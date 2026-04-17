#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Phone 1 - Local Self-Test
# Run this on Phone 1 BEFORE creating the tunnel
# Validates that Termux is properly configured
# ============================================

PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

test_pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
test_fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }

echo "============================================"
echo "  Phone 1 - Local Self-Test"
echo "============================================"
echo ""

# Test 1: SSH installed
echo "[Test 1/8] OpenSSH installed"
if command -v sshd &>/dev/null; then
    test_pass "sshd found: $(which sshd)"
else
    test_fail "sshd not found. Run: pkg install openssh"
fi

# Test 2: SSH running
echo "[Test 2/8] SSH server running"
if ss -tuln | grep -q ":8022"; then
    test_pass "SSH listening on port 8022"
else
    test_fail "SSH not running. Run: sshd"
fi

# Test 3: SSH local connection
echo "[Test 3/8] SSH local login"
LOCAL_TEST=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes \
    localhost -p 8022 "echo OK" 2>/dev/null)
if [ "$LOCAL_TEST" = "OK" ]; then
    test_pass "Can SSH to localhost:8022"
else
    test_fail "Cannot SSH locally (check password / keys)"
fi

# Test 4: tmux installed
echo "[Test 4/8] tmux installed"
if command -v tmux &>/dev/null; then
    test_pass "tmux found"
else
    test_fail "tmux not found. Run: pkg install tmux"
fi

# Test 5: Internet connectivity
echo "[Test 5/8] Internet access"
if ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then
    test_pass "Internet connectivity OK"
else
    test_fail "No internet access"
fi

# Test 6: DNS resolution
echo "[Test 6/8] DNS resolution"
if ping -c 1 -W 5 google.com >/dev/null 2>&1; then
    test_pass "DNS working"
else
    test_fail "DNS not working"
fi

# Test 7: Storage access
echo "[Test 7/8] Storage access (/sdcard)"
if [ -d "/sdcard" ] && [ -r "/sdcard" ]; then
    FILE_COUNT=$(ls /sdcard/ 2>/dev/null | wc -l)
    test_pass "/sdcard accessible ($FILE_COUNT items)"
else
    test_fail "/sdcard not accessible. Run: termux-setup-storage"
fi

# Test 8: Required tools
echo "[Test 8/8] Required tools"
MISSING=""
for tool in ssh curl ip ss; do
    if ! command -v $tool &>/dev/null; then
        MISSING="$MISSING $tool"
    fi
done
if [ -z "$MISSING" ]; then
    test_pass "All required tools available"
else
    test_fail "Missing tools:$MISSING"
fi

# Summary
echo ""
echo "============================================"
echo "  Self-Test Results: $PASS passed, $FAIL failed"
echo "============================================"
if [ $FAIL -eq 0 ]; then
    echo -e "  ${GREEN}🎉 Phone 1 is ready! Run start-tunnel.sh next.${NC}"
else
    echo -e "  ${RED}Fix the failures above before proceeding.${NC}"
fi
echo ""
