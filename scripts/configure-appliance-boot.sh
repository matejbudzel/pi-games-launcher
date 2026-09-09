#!/bin/sh
# Keep the boot path quiet and recover automatically from a kernel panic.
set -eu

cmdline=/boot/cmdline.txt
[ -f /boot/firmware/cmdline.txt ] && cmdline=/boot/firmware/cmdline.txt
[ -f "$cmdline" ] || { echo "No Raspberry Pi cmdline.txt found." >&2; exit 0; }
line=$(cat "$cmdline")
for setting in quiet splash logo.nologo loglevel=3 vt.global_cursor_default=0 panic=10; do
    case " $line " in *" $setting "*) ;; *) line="$line $setting" ;; esac
done
printf '%s\n' "$line" > "$cmdline"
