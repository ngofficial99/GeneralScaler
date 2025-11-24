# GeneralScaler - Testing Guide

This guide will help you test the GeneralScaler operator end-to-end with live scaling demonstrations.

## ✅ What's Already Set Up

- [x] kind cluster running (`generalscaler-demo`)
- [x] Prometheus deployed in `monitoring` namespace
- [x] Redis deployed in `default` namespace
- [x] Test application (`test-app`) deployed with 2 replicas
- [x] GeneralScaler CRD installed

## 🎯 Testing Options

### Option 1: Manual Testing (Easiest)

Test the scaling logic manually without running the full operator.

#### Terminal 1: Port-forward Redis

```bash
kubectl port-forward svc/redis 6379:6379
```

#### Terminal 2: Watch the Deployment

```bash
watch -n 2 'kubectl get deployment test-app'
```

#### Terminal 3: Run the Scaling Demo

```bash
source venv/bin/activate
python test_scaling_demo.py
```

This script will:
- Monitor the Redis queue length every 15 seconds
- Calculate desired replicas based on queue length
- Apply scaling decisions with cooldown/rate limits
- Show live updates of the scaling process

#### Terminal 4: Generate Load

```bash
# Add 30 items to the queue (will trigger scale-up)
source venv/bin/activate
python generate_load.py --count 30 --rate 10

# Wait and watch scaling happen...

# Add more load to scale up further
python generate_load.py --count 100 --rate 20

# Clear the queue to trigger scale-down
python -c "import redis; r=redis.Redis(); r.delete('test-queue'); print('Queue cleared')"
```

---

###  Option 2: Manual Kubernetes Scaling

Test the scaler components directly:

```bash
# Activate environment
source venv/bin/activate

# Scale up manually
kubectl scale deployment test-app --replicas=5

# Check current replicas
kubectl get deployment test-app

# Scale down
kubectl scale deployment test-app --replicas=2
```

---

### Option 3: Unit Test the Components

Test individual components:

```bash
source venv/bin/activate

# Test all units
pytest tests/unit/ -v

# Test specific component
pytest tests/unit/test_policies.py -v
pytest tests/unit/test_scaler.py::TestSafeScaler::test_scale_decision_respects_max_increment -v
```

---

## 📊 Expected Scaling Behavior

### Test Scenario 1: Scale Up

1. **Initial state**: 2 replicas, queue length = 0
2. **Add load**: Push 50 items to queue (queue length = 50)
3. **Expected**:
   - Target is 10 items/pod
   - Policy calculates: 50 / 10 = 5 replicas needed
   - Safety limits to max increment of 3
   - **Result**: Scales from 2 → 5 replicas
4. **Cooldown**: Waits 30 seconds before next scale-up

### Test Scenario 2: Scale Down

1. **Current state**: 5 replicas, queue length = 50
2. **Clear queue**: Delete all items (queue length = 0)
3. **Expected**:
   - Need only 1 replica (min is 1)
   - Safety limits to max decrement of 2
   - **Result**: Scales from 5 → 3 replicas
4. **Wait 60s cooldown**
5. **Next cycle**: Scales from 3 → 1 replica

### Test Scenario 3: Cost Constraints

- Max monthly cost: $1000
- Cost per pod: $0.05/hour
- Max affordable pods: ~13 pods
- Even if queue has 500 items, won't scale beyond 13 replicas

---

## 🔍 Monitoring Commands

```bash
# Watch deployment
kubectl get deployment test-app -w

# Check pods
kubectl get pods -l app=test-app

# Check Redis queue length
kubectl exec -it deploy/redis -- redis-cli LLEN test-queue

# View operator logs (if running)
tail -f operator.log

# Check CRD
kubectl get crd generalscalers.autoscaling.generalscaler.io

# View all resources
kubectl get all
```

---

## 🐛 Troubleshooting

### Redis connection issues

```bash
# Check Redis is running
kubectl get pods -l app=redis

# Test connectivity
kubectl exec -it deploy/redis -- redis-cli ping
# Should return: PONG

# Port-forward if needed
kubectl port-forward svc/redis 6379:6379
```

### Demo script issues

```bash
# Check Python environment
source venv/bin/activate
python --version  # Should be 3.9+

# Test imports
python -c "from generalscaler.scaler import SafeScaler; print('✅ OK')"

# Check kubectl access
kubectl get nodes
```

### Deployment not scaling

```bash
# Verify deployment exists
kubectl get deployment test-app

# Check current replicas
kubectl get deployment test-app -o jsonpath='{.spec.replicas}'

# Manual scale test
kubectl scale deployment test-app --replicas=3
kubectl get deployment test-app
```

---

## 🎬 Quick Demo Script

Run this complete test scenario:

```bash
# Terminal 1: Setup
source venv/bin/activate
kubectl port-forward svc/redis 6379:6379 &
sleep 2

# Terminal 2: Start the scaling demo
python test_scaling_demo.py &
DEMO_PID=$!

# Terminal 3: Watch it work
watch -n 1 'kubectl get deployment test-app; echo "---"; kubectl exec -it deploy/redis -- redis-cli LLEN test-queue 2>/dev/null || echo "Checking..."'

# Terminal 4: Generate load
sleep 5
python generate_load.py --count 50 --rate 10
echo "Added load! Watch the scaling happen..."

sleep 30
echo "Adding more load..."
python generate_load.py --count 100 --rate 20

sleep 60
echo "Clearing queue to trigger scale-down..."
python -c "import redis; r=redis.Redis(); r.delete('test-queue'); print('✅ Queue cleared')"

# Watch it scale down...
sleep 120

# Cleanup
kill $DEMO_PID
pkill -f "port-forward"
```

---

## 📈 Success Criteria

✅ **Scale Up**: Deployment scales when queue length exceeds target
✅ **Scale Down**: Deployment scales down when queue is empty
✅ **Cooldown**: Respects cooldown periods between scaling operations
✅ **Rate Limits**: Doesn't scale by more than maxIncrement/maxDecrement
✅ **Bounds**: Respects minReplicas and maxReplicas
✅ **Cost Aware**: Doesn't exceed budget constraints

---

## 🧹 Cleanup

```bash
# Kill all background processes
pkill -f "port-forward"
pkill -f "test_scaling_demo"

# Delete kind cluster
kind delete cluster --name generalscaler-demo

# Or keep cluster for more testing
echo "Cluster kept for more testing"
```

---

## 💡 Tips

1. **Watch mode is your friend**: Use `watch` command to see live updates
2. **Multiple terminals**: Use at least 3 terminals for best experience
3. **Adjust timings**: Edit cooldown values in `test_scaling_demo.py` for faster testing
4. **Redis CLI**: `kubectl exec -it deploy/redis -- redis-cli` for manual queue manipulation
5. **Logs**: Check `operator.log` if running the full operator

Happy Testing! 🚀
