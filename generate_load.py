#!/usr/bin/env python3
"""Generate artificial load by adding items to Redis queue."""

import sys
import time
import redis
import argparse


def main():
    parser = argparse.ArgumentParser(description="Generate load on Redis queue")
    parser.add_argument("--host", default="localhost", help="Redis host")
    parser.add_argument("--port", type=int, default=6379, help="Redis port")
    parser.add_argument("--queue", default="test-queue", help="Queue name")
    parser.add_argument("--count", type=int, default=50, help="Number of items to add")
    parser.add_argument("--rate", type=int, default=5, help="Items per second")

    args = parser.parse_args()

    print(f"🔥 Load Generator")
    print(f"Target: {args.host}:{args.port}, Queue: {args.queue}")
    print(f"Adding {args.count} items at {args.rate}/second")
    print("-" * 60)

    try:
        # Connect to Redis
        r = redis.Redis(host=args.host, port=args.port, decode_responses=True)
        r.ping()
        print(f"✅ Connected to Redis")

        # Get initial queue length
        initial_length = r.llen(args.queue)
        print(f"📊 Initial queue length: {initial_length}")

        # Add items
        delay = 1.0 / args.rate
        for i in range(args.count):
            item = f"job-{int(time.time())}-{i}"
            r.rpush(args.queue, item)
            current_length = r.llen(args.queue)
            print(f"  [{i+1}/{args.count}] Added '{item}' | Queue length: {current_length}")

            if i < args.count - 1:
                time.sleep(delay)

        final_length = r.llen(args.queue)
        print("-" * 60)
        print(f"✅ Done! Queue length: {initial_length} → {final_length}")

    except redis.ConnectionError as e:
        print(f"❌ Could not connect to Redis: {e}")
        print("\n💡 Tip: Port-forward Redis first:")
        print(f"   kubectl port-forward svc/redis 6379:6379")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
