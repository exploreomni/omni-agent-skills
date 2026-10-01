#!/usr/bin/env bash
# Publish the Peloton Product Comparison app to an Omni instance with the Omni CLI (>= 1.4.0).
#
#   1. omni config init --name demo --endpoint https://omni.demo.exploreomni.dev --auth oauth
#   2. ./publish-demo.sh demo                 # lists shared models if more than one
#   3. ./publish-demo.sh demo <shared-model-id>
#
# Creates ONE published app document in a single v2-create call: the app HTML plus three raw-SQL
# workbook tabs (peloton_products, peloton_monthly_sales, peloton_engagement) that the app wires to.
# The SQL is Snowflake syntax (VALUES + GENERATOR); on another warehouse the tabs will error and the
# app falls back to its embedded sample data until the tabs are rewritten.
set -euo pipefail
cd "$(dirname "$0")"
PROFILE="${1:-demo}"; MODEL_ID="${2:-}"; NAME="${3:-Peloton Product Comparison}"
command -v omni >/dev/null || { echo "Omni CLI not found: https://github.com/exploreomni/cli#readme" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required to build the request body" >&2; exit 1; }

echo "== whoami ($PROFILE)"; omni -p "$PROFILE" whoami whoami -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ", d.get("email") or d.get("name") or d, "|", d.get("role") or "")'

if [ -z "$MODEL_ID" ]; then
  echo "== shared models (pass one as the second argument)"
  omni -p "$PROFILE" models list --model-kind SHARED --explorable true -o json | python3 -c '
import json,sys; d=json.load(sys.stdin); recs=d.get("records") or d.get("data") or d
for m in recs: print(" ", m.get("id"), "|", m.get("name"))'
  exit 1
fi

mkdir -p archive
python3 - "$MODEL_ID" "$NAME" > archive/create-body.json <<'PY'
import json,sys
model_id,name=sys.argv[1],sys.argv[2]
html=open('app.html').read()
def tile(sql_file,label):
    sql=open(sql_file).read()
    return {"name":label,"type":"query","isSql":True,"prefersChart":False,"automaticVis":False,
            "query":{"fields":[],"userEditedSQL":sql,"table":"","limit":5000,"join_paths_from_topic_name":"",
                     "sorts":[],"filters":{},"calculations":[],"column_totals":{},"row_totals":{},"fill_fields":[],"pivots":[]}}
body={"modelId":model_id,"name":name,"description":"Interactive product comparison prototype (Omni App). Sample data until the SQL tabs point at real tables.",
      "app":{"html":html},
      "queryPresentations":{"data":{"1":tile('sql/peloton_products.sql','peloton_products'),
                                    "2":tile('sql/peloton_monthly_sales.sql','peloton_monthly_sales'),
                                    "3":tile('sql/peloton_engagement.sql','peloton_engagement')},
                            "order":["1","2","3"]}}
json.dump(body,sys.stdout)
PY
echo "== creating and publishing \"$NAME\" on model $MODEL_ID"
omni -p "$PROFILE" documents v2-create --body @archive/create-body.json -o json | tee archive/create-result.json | python3 -c '
import json,sys; d=json.load(sys.stdin)
print("  identifier:", d.get("identifier")); print("  warnings:", d.get("warnings") or "none")'
IDENT=$(python3 -c 'import json; print(json.load(open("archive/create-result.json"))["identifier"])')
echo "== queries on the new document"; omni -p "$PROFILE" documents get-queries "$IDENT" -o json | python3 -c '
import json,sys; d=json.load(sys.stdin); qs=d.get("queries") or d
for q in qs: print(" ", q.get("name"), "| key", q.get("queryIdentifierMapKey"))'
BASE=$(omni -p "$PROFILE" config show -o json 2>/dev/null | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin); p=d.get("profiles",{}).get(d.get("active") or d.get("activeProfile") or "",{}); print(p.get("apiEndpoint") or "")
except Exception: print("")')
echo "== done. Open: ${BASE:-https://<instance>}/w/$IDENT?redirectToApp=true"
echo "   If the header pill says 'Sample data', open the workbook, run each SQL tab once, and publish."
