import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { imageUrl } from "@web/core/utils/urls";

const STATUS_LABELS = {
    ongoing: "En cours",
    joined: "À commencer",
    completed: "Terminée",
};
const STATUS_BADGE_CLASS = {
    ongoing: "vn-badge-warning",
    joined: "vn-badge-neutral",
    completed: "vn-badge-success",
};

// "Mes formations" : vue personnelle sur les inscriptions eLearning de
// l'utilisateur, dans le meme esprit que Portfolio/Mes taches - le natif
// n'a pas d'equivalent condense montrant d'un coup ce qu'il reste a
// terminer, seulement le catalogue complet ou le lecteur d'un cours.
export class VillaNovaMyTrainings extends Component {
    static template = "villa_nova_elearning.MyTrainings";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.imageUrl = imageUrl;
        this.STATUS_LABELS = STATUS_LABELS;
        this.STATUS_BADGE_CLASS = STATUS_BADGE_CLASS;

        this.state = useState({ loading: true, trainings: [] });

        onWillStart(async () => {
            this.state.trainings = await this.orm.call(
                "slide.channel.partner", "get_villa_nova_my_trainings", []
            );
            this.state.loading = false;
        });
    }

    get summary() {
        const counts = { ongoing: 0, joined: 0, completed: 0 };
        for (const t of this.state.trainings) {
            counts[t.member_status] = (counts[t.member_status] || 0) + 1;
        }
        return counts;
    }

    courseImageUrl(channelId) {
        return this.imageUrl("slide.channel", channelId, "image_256");
    }

    openCourse(training) {
        if (training.website_url) {
            window.location.href = training.website_url;
        }
    }
}

registry.category("actions").add("villa_nova_elearning.my_trainings", VillaNovaMyTrainings);
