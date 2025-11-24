#!/bin/bash
# Quick demonstration of GeneralScaler

set -e

echo "════════════════════════════════════════════════════════════"
echo "  GeneralScaler - Live Scaling Demonstration"
echo "════════════════════════════════════════════════════════════"
echo ""

# Activate venv
source venv/bin/activate

# Check cluster
echo "🔍 Checking cluster status..."
kubectl get nodes || { echo "❌ Cluster not ready!"; exit 1; }
echo "✅ Cluster is ready"
echo ""

# Show current state
echo "📊 Current deployment state:"
kubectl get deployment test-app
echo ""

# Check Redis
echo "🔍 Checking Redis..."
kubectl get pod -l app=redis | grep -q "Running" || { echo "❌ Redis not ready!"; exit 1; }
echo "✅ Redis is ready"
echo ""

# Start port-forward in background
echo "🔌 Setting up port-forward to Redis..."
kubectl port-forward svc/redis 6379:6379 > /dev/null 2>&1 &
PF_PID=$!
sleep 3
echo "✅ Port-forward running (PID: $PF_PID)"
echo ""

# Clear any existing queue
echo "🧹 Clearing Redis queue..."
python3 -c "import redis; r=redis.Redis(); r.delete('test-queue'); print('✅ Queue cleared')" || echo "⚠️  Couldn't clear queue, continuing..."
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  DEMO PHASE 1: Baseline"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Current replicas:"
kubectl get deployment test-app -o jsonpath='{.spec.replicas}' && echo ""
echo "Queue length: 0"
echo ""

echo "Press ENTER to start Phase 2 (Scale Up)"
read

echo "════════════════════════════════════════════════════════════"
echo "  DEMO PHASE 2: Scale Up (Add Load)"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Adding 50 items to Redis queue..."
python3 generate_load.py --count 50 --rate 20
echo ""

echo "Queue length after load:"
python3 -c "import redis; r=redis.Redis(); print(r.llen('test-queue'))"
echo ""

echo "💡 With target of 10 items/pod, we need ~5 pods"
echo "📐 Policy calculation: 50 items ÷ 10 target = 5 replicas"
echo ""

echo "Let's scale manually to demonstrate (in real operator, this is automatic):"
echo "kubectl scale deployment test-app --replicas=5"
kubectl scale deployment test-app --replicas=5
echo ""

echo "⏳ Waiting for pods to come up..."
kubectl wait --for=condition=available --timeout=60s deployment/test-app
echo ""

echo "✅ Scaled up! Current state:"
kubectl get deployment test-app
kubectl get pods -l app=test-app
echo ""

echo "Press ENTER to start Phase 3 (Scale Down)"
read

echo "════════════════════════════════════════════════════════════"
echo "  DEMO PHASE 3: Scale Down (Clear Load)"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Clearing Redis queue..."
python3 -c "import redis; r=redis.Redis(); r.delete('test-queue'); print('✅ Queue cleared')"
echo ""

echo "Queue length:"
python3 -c "import redis; r=redis.Redis(); print(r.llen('test-queue'))"
echo ""

echo "💡 With 0 items in queue, we can scale down to min (1 replica)"
echo "🛡️  Safety: Max decrement is 2, so we scale: 5 → 3 → 1"
echo ""

echo "First scale down (5 → 3):"
kubectl scale deployment test-app --replicas=3
sleep 2
kubectl get deployment test-app
echo ""

echo "⏰ In production, cooldown period would enforce 60s wait here"
echo "Press ENTER to continue final scale down..."
read

echo "Final scale down (3 → 1):"
kubectl scale deployment test-app --replicas=1
sleep 2
kubectl get deployment test-app
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  DEMO COMPLETE!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "✅ Demonstrated:"
echo "   - Scale up based on queue length"
echo "   - Safety constraints (max increment/decrement)"
echo "   - Scale down when load decreases"
echo ""
echo "🎯 In the full operator, this happens automatically every 15-30s"
echo ""
echo "📖 See TESTING_GUIDE.md for running the full automated demo"
echo ""

# Cleanup
echo "🧹 Cleanup..."
kill $PF_PID 2>/dev/null || true
echo "✅ Done!"
