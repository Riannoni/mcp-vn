#!/usr/bin/env bash
set -euo pipefail
cd /home/Xavok/.local/share/mcp-vn-kobold/bin
file=koboldcpp-rocm
sum=418016f2d0945a1b3092cba53ff16a76224e289f7c47284ca3115962152ba71d
if [[ ! -f "$file" ]]; then
  curl -fsSL --retry 5 --retry-delay 4 --connect-timeout 25 --continue-at - \
    -o "$file.partial" \
    "https://github.com/LostRuins/koboldcpp/releases/download/rocm-rolling/koboldcpp-linux-x64-rocm"
  printf "%s  %s\n" "$sum" "$file.partial" | sha256sum -c -
  mv -- "$file.partial" "$file"
fi
printf "%s  %s\n" "$sum" "$file" | sha256sum -c -
test "$(stat -c '%s' "$file")" = 661999280
chmod 700 "$file"
echo ROCM_BINARY_VERIFIED
