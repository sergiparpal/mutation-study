#!/bin/bash
P=$1; B=$2
if ! defects4j bids -p $P | grep -qx "$B"; then
  echo "Bug $P-$B no válido o deprecado"; exit 1
fi
defects4j checkout -p $P -v ${B}b -w /tmp/${P}_${B}_b
defects4j checkout -p $P -v ${B}f -w /tmp/${P}_${B}_f
SRC=$(defects4j export -p dir.src.classes -w /tmp/${P}_${B}_b 2>/dev/null | tail -1)
diff -ru /tmp/${P}_${B}_b/$SRC /tmp/${P}_${B}_f/$SRC
