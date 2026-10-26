#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/.local/share/mcp-vn-comfy/models"
repo="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files"
fetch_model() {
  local section="$1" file="$2" bytes="$3" out="$base/$section/$file"
  mkdir -p "$(dirname "$out")"
  if [[ -f "$out" && "$(stat -c %s "$out")" == "$bytes" ]]; then
    echo "Already verified: $file"
    return
  fi
  echo "Downloading $file"
  curl --fail --silent --show-error --location --retry 5 --retry-delay 10 \
       --continue-at - --output "$out.part" "$repo/$section/$file"
  local received
  received="$(stat -c %s "$out.part")"
  [[ "$received" == "$bytes" ]] || { echo "Size mismatch $file: got $received expected $bytes"; exit 1; }
  mv "$out.part" "$out"
  echo "Verified $file ($bytes bytes)"
}
fetch_model vae wan2.2_vae.safetensors 1409400960
fetch_model text_encoders umt5_xxl_fp8_e4m3fn_scaled.safetensors 6735906897
fetch_model diffusion_models wan2.2_ti2v_5B_fp16.safetensors 9999658848
echo "Wan 2.2 TI2V 5B ready"
