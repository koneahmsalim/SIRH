// Package dpapi protege le secret d'agent au repos via l'API Windows DPAPI
// (CryptProtectData/CryptUnprotectData), en portee LocalMachine : le fichier
// de configuration chiffre n'est dechiffrable que sur CETTE machine (la clé
// de chiffrement est dérivée de secrets machine gérés par Windows, jamais
// exportée) - un fichier de config vole ne permet donc pas de rejouer les
// identifiants de l'agent sur une autre machine. Alternative deliberement
// preferee a un stockage en clair sur disque.
package dpapi

import (
	"fmt"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	modcrypt32           = windows.NewLazySystemDLL("crypt32.dll")
	modkernel32           = windows.NewLazySystemDLL("kernel32.dll")
	procCryptProtectData   = modcrypt32.NewProc("CryptProtectData")
	procCryptUnprotectData = modcrypt32.NewProc("CryptUnprotectData")
	procLocalFree          = modkernel32.NewProc("LocalFree")
)

type dataBlob struct {
	cbData uint32
	pbData *byte
}

func newBlob(data []byte) *dataBlob {
	if len(data) == 0 {
		return &dataBlob{}
	}
	return &dataBlob{cbData: uint32(len(data)), pbData: &data[0]}
}

func (b *dataBlob) bytes() []byte {
	if b.pbData == nil || b.cbData == 0 {
		return nil
	}
	return unsafe.Slice(b.pbData, b.cbData)
}

// Protect chiffre data pour la machine locale (portee CRYPTPROTECT_LOCAL_MACHINE,
// pas la portee "utilisateur courant" - l'agent tourne en tant que service
// LocalSystem, sans session utilisateur interactive associee).
func Protect(data []byte) ([]byte, error) {
	in := newBlob(data)
	var out dataBlob
	const CRYPTPROTECT_LOCAL_MACHINE = 0x4
	ret, _, err := procCryptProtectData.Call(
		uintptr(unsafe.Pointer(in)), 0, 0, 0, 0,
		uintptr(CRYPTPROTECT_LOCAL_MACHINE), uintptr(unsafe.Pointer(&out)),
	)
	if ret == 0 {
		return nil, fmt.Errorf("CryptProtectData: %w", err)
	}
	defer procLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)))
	result := make([]byte, out.cbData)
	copy(result, out.bytes())
	return result, nil
}

func Unprotect(data []byte) ([]byte, error) {
	in := newBlob(data)
	var out dataBlob
	ret, _, err := procCryptUnprotectData.Call(
		uintptr(unsafe.Pointer(in)), 0, 0, 0, 0, 0, uintptr(unsafe.Pointer(&out)),
	)
	if ret == 0 {
		return nil, fmt.Errorf("CryptUnprotectData: %w", err)
	}
	defer procLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)))
	result := make([]byte, out.cbData)
	copy(result, out.bytes())
	return result, nil
}
