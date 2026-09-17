from collections import OrderedDict

import babel.dates

from odoo import fields, models


def _pourcent(valeur):
    """'87 %' - l'espace insecable evite que le signe passe seul a la ligne."""
    return '%d %%' % int(round(valeur or 0))


def _date_courte(d):
    """'mar. 1 sept. 2026' - le jour de la semaine est ce qui permet de reperer
    un motif (les lundis, les lendemains de ferie) sans compter sur un calendrier."""
    try:
        return babel.dates.format_date(d, "EEE d MMM yyyy", locale='fr_FR')
    except Exception:
        return d.strftime('%d/%m/%Y')


def _date_longue(d):
    try:
        return babel.dates.format_date(d, "EEEE d MMMM yyyy", locale='fr_FR').capitalize()
    except Exception:
        return d.strftime('%d/%m/%Y')


class ReportVillaNovaAttendance(models.AbstractModel):
    _name = 'report.villa_nova_biometric_attendance.presence_report'
    _description = "Rapport de présence (retards / absences) - PDF"

    # ------------------------------------------------------------------
    # Regroupement
    # ------------------------------------------------------------------
    def _grouper(self, lignes, group_by, wizard, avec_retard):
        """Transforme une liste plate en blocs.

        Une liste a plat triee par date se lit correctement sur trois jours et
        devient illisible sur trois semaines : le nom et la date se repetent a
        chaque ligne, et suivre une personne oblige a parcourir tout le
        document. On regroupe donc, et chaque bloc porte son propre sous-total.
        """
        groupes = OrderedDict()

        if group_by == 'employee':
            ordre = sorted(lignes, key=lambda l: (l['employee'].name or '', l['date']))
            for l in ordre:
                emp = l['employee']
                g = groupes.setdefault(emp.id, {
                    'titre': emp.name,
                    'sous_titre': emp.department_id.name or '',
                    'lignes': [], 'nb': 0, 'minutes': 0,
                })
                g['lignes'].append({
                    'date_txt': _date_courte(l['date']),
                    'employe': emp.name,
                    'departement': emp.department_id.name or '—',
                    'heure': l['check_in_local'].strftime('%H:%M') if avec_retard else '',
                    'retard_txt': l.get('retard_txt', ''),
                })
                g['nb'] += 1
                g['minutes'] += l.get('delay_minutes', 0)
        else:
            ordre = sorted(lignes, key=lambda l: (l['date'], l['employee'].name or ''))
            for l in ordre:
                emp = l['employee']
                g = groupes.setdefault(l['date'], {
                    'titre': _date_longue(l['date']),
                    'sous_titre': '',
                    'lignes': [], 'nb': 0, 'minutes': 0,
                })
                g['lignes'].append({
                    'date_txt': _date_courte(l['date']),
                    'employe': emp.name,
                    'departement': emp.department_id.name or '—',
                    'heure': l['check_in_local'].strftime('%H:%M') if avec_retard else '',
                    'retard_txt': l.get('retard_txt', ''),
                })
                g['nb'] += 1
                g['minutes'] += l.get('delay_minutes', 0)

        # Resume de bloc : ce que la RH lit en premier avant d'entrer dans le detail.
        resultat = []
        for g in groupes.values():
            if avec_retard:
                g['resume'] = '%d retard%s · %s' % (
                    g['nb'], 's' if g['nb'] > 1 else '',
                    wizard._format_delay(g['minutes']))
            else:
                g['resume'] = '%d absence%s' % (g['nb'], 's' if g['nb'] > 1 else '')
            resultat.append(g)
        return resultat

    # ------------------------------------------------------------------
    def _get_report_values(self, docids, data=None):
        wizards = self.env['villa.nova.attendance.report.wizard'].browse(docids)
        wizard = wizards[0]
        employees = wizard._get_employees()

        late_lines = wizard._compute_late_lines(employees) if wizard.report_type in ('all', 'late') else []
        absent_lines = wizard._compute_absent_lines(employees) if wizard.report_type in ('all', 'absent') else []

        # La synthese par employe n'est plus imprimee, mais elle reste calculee :
        # c'est elle qui porte les jours dus et la ponctualite, dont se deduisent
        # les chiffres de la periode. Seul son detail nominatif a ete retire.
        totaux = None
        if wizard.report_type == 'all':
            rows = wizard._compute_synthesis(employees, late_lines, absent_lines)
            totaux = wizard._totaux(rows)
            totaux['ponctualite_txt'] = _pourcent(totaux['ponctualite'])
            totaux['assiduite_txt'] = _pourcent(totaux['assiduite'])
            totaux['cumul_txt'] = wizard._format_delay(totaux['minutes_retard'])
            totaux['effectif_txt'] = '%d personnes' % totaux['effectif']

        # Tout le formatage est fait ici plutot que dans le gabarit : QWeb compile
        # ses attributs en chaines de format Python, ou un operateur "%" finit en
        # "ValueError: incomplete format" a l'execution. Formater dans le code a
        # aussi l'avantage de se tester.
        for line in late_lines:
            line['retard_txt'] = wizard._format_delay(line['delay_minutes'])

        # Le perimetre est rappele dans l'en-tete : un rapport de presence sans
        # ses filtres se prete a toutes les lectures, y compris les mauvaises.
        if wizard.employee_ids:
            perimetre = '%d employé(s) sélectionné(s)' % len(wizard.employee_ids)
        elif wizard.department_id:
            perimetre = wizard.department_id.name
        else:
            perimetre = "Tout l'effectif badgé"

        return {
            'doc_ids': docids,
            'doc_model': 'villa.nova.attendance.report.wizard',
            'docs': wizards,
            'totaux': totaux,
            'groupes_retards': self._grouper(late_lines, wizard.group_by, wizard, True),
            'groupes_absences': self._grouper(absent_lines, wizard.group_by, wizard, False),
            'par_employe': wizard.group_by == 'employee',
            'threshold_label': wizard._format_threshold(),
            'perimetre': perimetre,
            'effectif_txt': ('%d personnes' % len(employees)) if employees else '—',
            'date_edition': fields.Date.today(),
        }
