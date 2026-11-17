#!/bin/bash
set -euo pipefail

# This runs only on the ephemeral macOS signing runner, before Tauri seals
# the Resources directory containing the PyInstaller payload.
cert="$RUNNER_TEMP/skellyclicker-identity.p12"
keychain="$RUNNER_TEMP/skellyclicker-signing.keychain-db"
password="$(openssl rand -hex 32)"
trap 'rm -f "$cert"' EXIT
printf '%s' "${MAC_CERTIFICATE_P12:?missing Developer ID certificate}" | base64 -D > "$cert"
security create-keychain -p "$password" "$keychain"
security set-keychain-settings -lut 21600 "$keychain"
security unlock-keychain -p "$password" "$keychain"
security import "$cert" -k "$keychain" -P "${MAC_CERTIFICATE_PASSWORD:?missing certificate password}" -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$password" "$keychain" >/dev/null
security list-keychains -d user -s "$keychain" "$HOME/Library/Keychains/login.keychain-db"

while IFS= read -r -d '' binary; do
  if [[ "$(file -b "$binary")" == *Mach-O* ]]; then
    options=(--force --timestamp --options runtime --sign "$APPLE_SIGNING_IDENTITY")
    if [[ "$binary" == */tools/node ]]; then
      options+=(--preserve-metadata=entitlements)
    fi
    codesign "${options[@]}" "$binary"
  fi
done < <(find native/binaries/skellyclicker-backend -type f -print0)
