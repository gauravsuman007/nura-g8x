#!/bin/sh
# Flash a boot.img only if its pmos root/boot UUIDs match the userdata installed on the phone.
# Usage: devtools/flash-boot-safe.sh boot.img   (phone must be reachable by ssh; then put it in fastboot)
# A mismatching image leaves the phone in the initramfs (no python there to get back to fastboot).
set -e
img=$1; key=${KEY:-out/sshkey/g8x}; host=${HOST:-user@172.16.42.1}
want=$(ssh -i "$key" "$host" 'cat /proc/cmdline' </dev/null | tr ' ' '\n' | grep -E '^pmos_(boot|root)_uuid=' | sort)
have=$(strings -n 8 "$img" | tr ' ' '\n' | grep -E '^pmos_(boot|root)_uuid=' | sort)
[ -n "$want" ] && [ "$want" = "$have" ] || { echo "REFUSING: UUID mismatch"; echo "phone:"; echo "$want"; echo "image:"; echo "$have"; exit 1; }
echo "UUIDs match; flashing"
fastboot flash boot_b "$img"
