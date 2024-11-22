#! /usr/bin/env bash

PODIR=po
POFILE="${PODIR}/pisi.po"
POTFILE="${PODIR}/pisi.pot"

rm "${POFILE}" -f
touch "${POFILE}"

find pisi -name "*.py" -exec xgettext -L "Python" --join-existing --no-wrap --add-comments --from-code=UTF-8 -o "${POFILE}" {} \;

mv "${POFILE}" "${POTFILE}"
echo "Translatable strings compiled. Upload them to Transifex with: \`tx push -s\`"
