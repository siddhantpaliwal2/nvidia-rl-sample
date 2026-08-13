#!/bin/sh
set -u

REPO_DIR=""
for d in /app /testbed; do
    if [ -d "$d/.git" ] && [ -f "$d/src/groovy/com/bankScraper/bank/BankTransactionUtil.groovy" ]; then
        REPO_DIR="$d"
        break
    fi
done
[ -n "$REPO_DIR" ] || { echo "run_script.sh: repository not found" >&2; exit 2; }
cd "$REPO_DIR"

rm -rf /tmp/finbit-verifier-classes /tmp/finbit-verifier-source
mkdir -p /tmp/finbit-verifier-classes /tmp/finbit-verifier-source/com/bankScraper/bank/pdf /tmp/finbit-verifier-source/com/bankScraper/bank
cp src/groovy/com/bankScraper/bank/BankTransactionUtil.groovy /tmp/finbit-verifier-source/com/bankScraper/bank/
cp grails-app/services/com/bankScraper/bank/pdf/AndhraBankPdfService.groovy /tmp/finbit-verifier-source/com/bankScraper/bank/pdf/
cp grails-app/services/com/bankScraper/bank/pdf/BankOfBarodaPdfService.groovy /tmp/finbit-verifier-source/com/bankScraper/bank/pdf/

GRAILS_HOME="${GRAILS_HOME:-/opt/grails-2.3.11}"
GRAILS_CP="$(find "$GRAILS_HOME" -name '*.jar' -print | tr '\n' ':')"
java -cp "$GRAILS_CP" org.codehaus.groovy.tools.FileSystemCompiler \
    -d /tmp/finbit-verifier-classes \
    $(find xai-tests/stubs -name '*.groovy' -print) || exit 0

rm -f /tmp/finbit-unit.json
java -cp "/tmp/finbit-verifier-classes:${GRAILS_CP}/tmp/finbit-verifier-source:$REPO_DIR/lib/*" \
    groovy.ui.GroovyMain xai-tests/finbit_parser_spec.groovy 2>&1 || true
