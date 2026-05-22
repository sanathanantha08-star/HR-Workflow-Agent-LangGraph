#!/bin/bash
# End-to-end test for the HR Workflow.
# Usage: bash test_flow.sh path/to/your_resume.pdf
# Make sure the server is running: python main.py

BASE=http://localhost:8000
RESUME=${1:-"your_resume.pdf"}
JD="test_jd.txt"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}=== HR Workflow End-to-End Test ===${NC}\n"

# ── Step 1: Upload resume + JD ─────────────────────────────────────────────
echo -e "${BOLD}[1/5] Uploading resume and JD...${NC}"
RESPONSE=$(curl -s -X POST "$BASE/api/workflow/start" \
  -F "jd_file=@$JD;type=text/plain" \
  -F "resume_files=@$RESUME;type=application/pdf")

echo "$RESPONSE" | python3 -m json.tool
SESSION_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo -e "\n${GREEN}Session ID: $SESSION_ID${NC}\n"

if [ -z "$SESSION_ID" ]; then
  echo "Upload failed. Is the server running?"
  exit 1
fi

# ── Step 2: Poll until shortlisting is done ────────────────────────────────
echo -e "${BOLD}[2/5] Waiting for resume shortlisting (Cohere is analyzing)...${NC}"
for i in {1..30}; do
  sleep 5
  STEP=$(curl -s "$BASE/api/workflow/$SESSION_ID/status" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['current_step'])" 2>/dev/null)
  echo "  → current_step: $STEP"
  if [ "$STEP" = "resumes_shortlisted" ]; then
    break
  fi
  if [ "$STEP" = "error" ]; then
    echo "Graph hit an error. Check server logs."
    exit 1
  fi
done

# ── Step 3: Show shortlist ─────────────────────────────────────────────────
echo -e "\n${BOLD}[3/5] Shortlisted candidates:${NC}"
curl -s "$BASE/api/workflow/$SESSION_ID/shortlist" | python3 -m json.tool

echo -e "\n${YELLOW}Review the shortlist above, then press ENTER to approve...${NC}"
read

# ── Step 4: Approve shortlist (HITL Gate 1) ────────────────────────────────
echo -e "\n${BOLD}[4/5] Approving shortlist (HITL Gate 1)...${NC}"
curl -s -X POST "$BASE/api/hitl/$SESSION_ID/shortlist" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "feedback": "Looks good, proceed to pre-screening"}' \
  | python3 -m json.tool

echo -e "\n${YELLOW}Pre-screening call will be initiated to your number.${NC}"
echo -e "${YELLOW}Answer the call and complete the conversation, then press ENTER...${NC}"
read

# ── Step 5: Show pre-screening results ────────────────────────────────────
echo -e "\n${BOLD}[5/5] Pre-screening results:${NC}"
curl -s "$BASE/api/workflow/$SESSION_ID/pre-screening" | python3 -m json.tool

echo -e "\n${YELLOW}Review results above, then press ENTER to approve and complete workflow...${NC}"
read

curl -s -X POST "$BASE/api/hitl/$SESSION_ID/pre-screening" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "feedback": "Pre-screening complete, move to interview stage"}' \
  | python3 -m json.tool

echo -e "\n${GREEN}=== Workflow complete! ===${NC}"
echo "Final status:"
curl -s "$BASE/api/workflow/$SESSION_ID/status" | python3 -m json.tool
