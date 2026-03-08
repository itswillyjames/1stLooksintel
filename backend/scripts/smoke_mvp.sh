#!/bin/bash
# Permit Intel MVP Smoke Test
# Tests the complete happy path: seed → report → version → scope_summary → export

set -e

API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
IDEMPOTENCY_KEY="smoke-001"

echo "=========================================="
echo "Permit Intel MVP Smoke Test"
echo "=========================================="
echo "API URL: $API_URL"
echo "Idempotency Key: $IDEMPOTENCY_KEY"
echo ""

# Step 1: Seed permits
echo "Step 1: Seeding permits..."
SEED_RESULT=$(curl -s -X POST "$API_URL/api/permits/seed" -H "Content-Type: application/json" -d '{}')
echo "Seed result: $SEED_RESULT"
echo ""

# Step 2: Get first permit
echo "Step 2: Getting first permit..."
PERMIT_ID=$(curl -s "$API_URL/api/permits?limit=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['permits'][0]['id'])")
echo "Permit ID: $PERMIT_ID"
echo ""

# Step 3: Create report
echo "Step 3: Creating report..."
REPORT_RESULT=$(curl -s -X POST "$API_URL/api/reports" -H "Content-Type: application/json" -d "{\"permit_id\":\"$PERMIT_ID\"}")
REPORT_ID=$(echo "$REPORT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Report ID: $REPORT_ID"
echo ""

# Step 4: Create version
echo "Step 4: Creating report version..."
VERSION_RESULT=$(curl -s -X POST "$API_URL/api/reports/$REPORT_ID/versions" -H "Content-Type: application/json")
VERSION_ID=$(echo "$VERSION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Version ID: $VERSION_ID"
echo ""

# Step 5: Run scope_summary
echo "Step 5: Running scope_summary stage..."
STAGE_RESULT=$(curl -s -X POST "$API_URL/api/reports/versions/$VERSION_ID/stages/scope_summary/run" \
  -H "Content-Type: application/json" \
  -d "{\"idempotency_key\":\"$IDEMPOTENCY_KEY\"}")
STAGE_STATUS=$(echo "$STAGE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['attempt']['status'])")
IS_RERUN_STAGE=$(echo "$STAGE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_rerun', False))")
echo "Stage status: $STAGE_STATUS"
echo "Is rerun: $IS_RERUN_STAGE"
echo ""

# Step 6: Render export
echo "Step 6: Rendering dossier export..."
EXPORT_RESULT=$(curl -s -X POST "$API_URL/api/reports/versions/$VERSION_ID/exports/dossier/render" \
  -H "Content-Type: application/json" \
  -d "{\"template_version\":\"v1\",\"idempotency_key\":\"$IDEMPOTENCY_KEY\"}")
EXPORT_ID=$(echo "$EXPORT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['export']['id'])")
EXPORT_STATUS=$(echo "$EXPORT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['export']['status'])")
IS_RERUN_EXPORT=$(echo "$EXPORT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_rerun', False))")
echo "Export ID: $EXPORT_ID"
echo "Export status: $EXPORT_STATUS"
echo "Is rerun: $IS_RERUN_EXPORT"
echo ""

# Step 7: Verify HTML content
echo "Step 7: Verifying HTML content..."
HTML_CONTENT=$(curl -s "$API_URL/api/exports/$EXPORT_ID?format=html")
if echo "$HTML_CONTENT" | grep -q "Permit Intelligence Dossier"; then
  HTML_CHECK="PASS"
else
  HTML_CHECK="FAIL"
fi
echo "HTML contains 'Permit Intelligence Dossier': $HTML_CHECK"
echo ""

# Step 8: Test idempotency (rerun)
echo "Step 8: Testing idempotency (rerun)..."
RERUN_RESULT=$(curl -s -X POST "$API_URL/api/reports/versions/$VERSION_ID/exports/dossier/render" \
  -H "Content-Type: application/json" \
  -d "{\"template_version\":\"v1\",\"idempotency_key\":\"$IDEMPOTENCY_KEY\"}")
RERUN_EXPORT_ID=$(echo "$RERUN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['export']['id'])")
RERUN_IS_RERUN=$(echo "$RERUN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_rerun', False))")
if [ "$RERUN_EXPORT_ID" = "$EXPORT_ID" ] && [ "$RERUN_IS_RERUN" = "True" ]; then
  IDEMPOTENCY_CHECK="PASS"
else
  IDEMPOTENCY_CHECK="FAIL"
fi
echo "Same export_id returned: $RERUN_EXPORT_ID"
echo "is_rerun=True: $RERUN_IS_RERUN"
echo "Idempotency check: $IDEMPOTENCY_CHECK"
echo ""

# Summary
echo "=========================================="
echo "SMOKE TEST SUMMARY"
echo "=========================================="
echo "Permit ID:    $PERMIT_ID"
echo "Report ID:    $REPORT_ID"
echo "Version ID:   $VERSION_ID"
echo "Export ID:    $EXPORT_ID"
echo ""
echo "Stage status:       $STAGE_STATUS"
echo "Export status:      $EXPORT_STATUS"
echo "HTML check:         $HTML_CHECK"
echo "Idempotency check:  $IDEMPOTENCY_CHECK"
echo ""

# Final result
if [ "$STAGE_STATUS" = "succeeded" ] && [ "$EXPORT_STATUS" = "ready" ] && [ "$HTML_CHECK" = "PASS" ] && [ "$IDEMPOTENCY_CHECK" = "PASS" ]; then
  echo "✅ SMOKE TEST PASSED"
  exit 0
else
  echo "❌ SMOKE TEST FAILED"
  exit 1
fi
