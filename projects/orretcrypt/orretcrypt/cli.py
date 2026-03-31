#!/usr/bin/env python3
"""
OrretCrypt CLI — Chiffrement post-quantique
==========================================
ML-KEM-768 (Kyber-768) + AES-256-GCM

Usage:
    python3 orretcrypt.py keygen [--dir <path>]
    python3 orretcrypt.py encrypt --key <pub.pem> --file <input> [--output <output.orret>]
    python3 orretcrypt.py decrypt --key <priv.pem> --file <input.orret> [--output <output>]
    python3 orretcrypt.py info --file <input.orret>
"""

import os
import sys
import argparse

# ─── Import from local core ───
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _orretcrypt_core import (
    KeyPair,
    encrypt_file,
    decrypt_file,
    info,
    OrretCryptError,
)

CSI_GREEN = '\033[92m'
CSI_RED = '\033[91m'
CSI_CYAN = '\033[96m'
CSI_DIM = '\033[2m'
CSI_RESET = '\033[0m'


def colored(color, text):
    return f"{color}{text}{CSI_RESET}"


def cmd_keygen(args):
    """Génère une clépair ML-KEM-768."""
    os.makedirs(args.dir, exist_ok=True)
    kp = KeyPair.generate()
    
    pub_path = os.path.join(args.dir, 'orretpub.pem')
    priv_path = os.path.join(args.dir, 'orretpriv.pem')
    
    # Private key: mode 600
    old_umask = os.umask(0o077)
    try:
        kp.save_private(priv_path)
    finally:
        os.umask(old_umask)
    kp.save_public(pub_path)
    
    print(f"\n  {colored(CSI_CYAN, '🔐')} KeyPair ML-KEM-768 générée")
    print(f"  {colored(CSI_DIM, '📄')} Clé publique : {pub_path}  ({len(kp.public_key)} octets)")
    print(f"  {colored(CSI_DIM, '🔒')} Clé privée  : {priv_path}  ({len(kp.private_key)} octets)")
    print(f"\n  {colored(CSI_GREEN, '✓')} Conservez votre clé privée en lieu sûr!")
    print(f"    Toute personne avec cette clé peut déchiffrer vos fichiers.")


def cmd_encrypt(args):
    """Chiffre un fichier."""
    pub_kp = KeyPair.load_public(args.key)
    out = encrypt_file(pub_kp.public_key, args.file, args.output)
    size_in = os.path.getsize(args.file)
    size_out = os.path.getsize(out)
    overhead = size_out - size_in
    print(f"\n  {colored(CSI_CYAN, '📦')} {args.file}")
    print(f"  {colored(CSI_DIM, '→')}  {out}")
    print(f"  {colored(CSI_DIM, '📊')} {size_in:,} octets → {size_out:,} octets (surcharge: +{overhead:,})")
    print(f"  {colored(CSI_GREEN, '✓')} Chiffré avec ML-KEM-768 + AES-256-GCM")


def cmd_decrypt(args):
    """Déchiffre un fichier .orret."""
    priv_kp = KeyPair.load_private(args.key)
    out = decrypt_file(priv_kp.private_key, args.file, args.output)
    size = os.path.getsize(out)
    print(f"\n  {colored(CSI_CYAN, '🔓')} {args.file}")
    print(f"  {colored(CSI_DIM, '→')}  {out}")
    print(f"  {colored(CSI_DIM, '📊')} {size:,} octets déchiffrés")
    print(f"  {colored(CSI_GREEN, '✓')} Succès")


def cmd_info(args):
    """Affiche les métadonnées d'un fichier .orret."""
    try:
        meta = info(args.file)
        print(f"\n  {colored(CSI_CYAN, '📋')} Fichier .orret")
        print(f"  {'─' * 40}")
        print(f"  Magic       : {meta['magic']} ({colored(CSI_GREEN, 'valide')})")
        print(f"  Version     : v{meta['version']}")
        print(f"  KEM         : {meta['kem_name']}")
        print(f"  PK stockée  : {meta['pk_len']} octets")
        print(f"  CT Kyber    : {meta['ct_kem_len']} octets")
        print(f"  CT données  : {meta['ct_len']:,} octets")
        print(f"  Total       : {meta['total_len']:,} octets")
        print(f"\n  {colored(CSI_GREEN, '✓')} Format valide")
    except OrretCryptError as e:
        print(f"\n  {colored(CSI_RED, '✗')} {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog='orretcrypt.py',
        description='OrretCrypt — Chiffrement post-quantique (ML-KEM-768 + AES-256-GCM)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 orretcrypt.py keygen --dir ./cles
  python3 orretcrypt.py encrypt --key pub.pem --file document.pdf
  python3 orretcrypt.py decrypt --key priv.pem --file document.pdf.orret
  python3 orretcrypt.py info --file document.pdf.orret
        """
    )
    
    sub = parser.add_subparsers(dest='cmd', required=True)
    
    p_keygen = sub.add_parser('keygen', help='Génère une clépair ML-KEM-768')
    p_keygen.add_argument('--dir', '-d', default='.', help='Répertoire de sortie')
    
    p_enc = sub.add_parser('encrypt', help='Chiffre un fichier')
    p_enc.add_argument('--key', '-k', required=True, help='Clé publique (.pem)')
    p_enc.add_argument('--file', '-f', required=True, help='Fichier à chiffrer')
    p_enc.add_argument('--output', '-o', help='Fichier de sortie')
    
    p_dec = sub.add_parser('decrypt', help='Déchiffre un fichier .orret')
    p_dec.add_argument('--key', '-k', required=True, help='Clé privée (.pem)')
    p_dec.add_argument('--file', '-f', required=True, help='Fichier à déchiffrer')
    p_dec.add_argument('--output', '-o', help='Fichier de sortie')
    
    p_info = sub.add_parser('info', help='Affiche les métadonnées')
    p_info.add_argument('--file', '-f', required=True, help='Fichier .orret')
    
    args = parser.parse_args()
    
    try:
        if args.cmd == 'keygen':
            cmd_keygen(args)
        elif args.cmd == 'encrypt':
            cmd_encrypt(args)
        elif args.cmd == 'decrypt':
            cmd_decrypt(args)
        elif args.cmd == 'info':
            cmd_info(args)
    except OrretCryptError as e:
        print(f"\n  {colored(CSI_RED, '✗ Erreur:')} {e}\n", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n  {colored(CSI_RED, '✗ Fichier non trouvé:')} {e}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
