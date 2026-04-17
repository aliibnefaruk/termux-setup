#!/bin/bash
# ============================================
# Connection Test Script
# Run this from PC / Phone 2 to verify setup
# Usage: ./test-connection.sh <VPS_USER> <VPS_IP> [TUNNEL_PORT]
# ============================================

VPS_USER="${1:-root}"
VPS_IP="${2:-93.127.195.64}"
TUNNEL_PORT="${3:-2222}"

PASS=0
FAIL=0
WARN=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

test_pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
test_fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
test_warn() { echo -e "  ${YELLOW}⚠️  WARN${NC}: $1"; WARN=$((WARN + 1)); }

echo "============================================"
echo "  Connection Test Suite"
echo "  Target: ${VPS_USER}@${VPS_IP}:${TUNNEL_PORT}"
echo "============================================"
echo ""

# --- Test 1: VPS Reachability ---
echo "[Test 1/7] VPS Reachability (ping)"
if ping -c 2 -W 5 "$VPS_IP" >/dev/null 2>&1; then
    test_pass "VPS $VPS_IP is reachable"
else
    test_warn "VPS $VPS_IP not pingable (ICMP may be blocked, continuing...)"
fi

# --- Test 2: VPS SSH Port ---
echo "[Test 2/7] VPS SSH Port (22)"
if timeout 5 bash -c "echo >/dev/tcp/$VPS_IP/22" 2>/dev/null; then
    test_pass "VPS SSH port 22 is open"
else
    test_fail "VPS SSH port 22 is not reachable"
fi

# --- Test 3: Tunnel Port Open ---
echo "[Test 3/7] Tunnel Port ($TUNNEL_PORT) on VPS"
if timeout 5 bash -c "echo >/dev/tcp/$VPS_IP/$TUNNEL_PORT" 2>/dev/null; then
    test_pass "Tunnel port $TUNNEL_PORT is open on VPS"
else
    # Try via SSH to VPS, check localhost
    echo "  Checking via SSH to VPS..."
    TUNNEL_CHECK=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "${VPS_USER}@${VPS_IP}" \
        "ss -tuln | grep :${TUNNEL_PORT}" 2>/dev/null)
    if [ -n "$TUNNEL_CHECK" ]; then
        test_pass "Tunnel port $TUNNEL_PORT is open (localhost on VPS)"
    else
        test_fail "Tunnel port $TUNNEL_PORT is NOT open — Phone 1 tunnel may be down"
    fi
fi

# --- Test 4: SSH Through Tunnel ---
echo "[Test 4/7] SSH Through Tunnel to Phone 1"
SSH_RESULT=$(ssh -o ConnectTimeout=15 -o BatchMode=yes \
    -J "${VPS_USER}@${VPS_IP}" \
    -p "$TUNNEL_PORT" localhost "echo CONNECTION_OK" 2>/dev/null)
if [ "$SSH_RESULT" = "CONNECTION_OK" ]; then
    test_pass "SSH through tunnel to Phone 1 works!"
else
    # Try direct port approach
    SSH_RESULT2=$(ssh -o ConnectTimeout=15 -o BatchMode=yes \
        -p "$TUNNEL_PORT" "${VPS_USER}@${VPS_IP}" "echo CONNECTION_OK" 2>/dev/null)
    if [ "$SSH_RESULT2" = "CONNECTION_OK" ]; then
        test_pass "SSH to Phone 1 via VPS:$TUNNEL_PORT works"
    else
        test_fail "Cannot SSH through tunnel to Phone 1"
    fi
fi

# --- Test 5: Run Command on Phone ---
echo "[Test 5/7] Execute Command on Phone 1"
PHONE_INFO=$(ssh -o ConnectTimeout=15 -o BatchMode=yes \
    -p "$TUNNEL_PORT" "${VPS_USER}@${VPS_IP}" \
    "whoami && uname -a" 2>/dev/null)
if [ -n "$PHONE_INFO" ]; then
    test_pass "Command execution works"
    echo "         Phone user: $(echo "$PHONE_INFO" | head -1)"
else
    test_fail "Cannot execute commands on Phone 1"
fi

# --- Test 6: File Access (SFTP) ---
echo "[Test 6/7] SFTP File Access"
SFTP_TEST=$(ssh -o ConnectTimeout=15 -o BatchMode=yes \
    -p "$TUNNEL_PORT" "${VPS_USER}@${VPS_IP}" \
    "ls /sdcard/ 2>/dev/null | head -5" 2>/dev/null)
if [ -n "$SFTP_TEST" ]; then
    test_pass "Can access /sdcard/ directory"
    echo "         Sample files: $(echo $SFTP_TEST | tr '\n' ', ')"
else
    test_warn "Cannot list /sdcard/ (may need storage permission in Termux)"
fi

# --- Test 7: Monitoring Capability ---
echo "[Test 7/7] Monitoring Capability"
MONITOR_TEST=$(ssh -o ConnectTimeout=15 -o BatchMode=yes \
    -p "$TUNNEL_PORT" "${VPS_USER}@${VPS_IP}" \
    "cat /proc/meminfo | head -3 && df -h /sdcard 2>/dev/null | tail -1" 2>/dev/null)
if [ -n "$MONITOR_TEST" ]; then
    test_pass "Can read system stats from Phone 1"
else
    test_fail "Cannot read system stats"
fi

# --- Summary ---
echo ""
echo "============================================"
echo "  Test Results"
echo "============================================"
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"
echo -e "  ${YELLOW}Warnings: $WARN${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "  ${GREEN}🎉 All critical tests passed!${NC}"
    echo "  Your Phone 1 → VPS → PC setup is working."
else
    echo -e "  ${RED}⚠️  Some tests failed. Check:${NC}"
    echo "  1. Is Phone 1 tunnel running? (start-tunnel.sh)"
    echo "  2. Is VPS SSH accessible?"
    echo "  3. VPS firewall allows port $TUNNEL_PORT?"
    echo "  4. SSH keys or password configured?"
fi
echo ""
