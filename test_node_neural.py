#!/usr/bin/env python3
"""Test script to verify neural network system is working in the node."""

import time

import requests


def test_neural_endpoints():
    """Test the neural network endpoints in the node."""
    base_url = "http://127.0.0.1:8001"  # Default API port

    print("🧠 Testing Neural Network Endpoints in Axiom Node")
    print("=" * 60)

    # Test 1: Neural fact verification
    print("\n1. Testing Neural Fact Verification...")
    test_fact = {
        "content": "The Earth orbits around the Sun in approximately 365.25 days.",
        "sources": [{"domain": "nasa.gov"}],
    }

    try:
        response = requests.post(
            f"{base_url}/neural/verify_fact", json=test_fact,
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ Neural verification endpoint working!")
            print(
                f"   Confidence: {result['verification_result']['confidence']:.3f}",
            )
            print(f"   Verified: {result['verification_result']['verified']}")
        else:
            print(f"❌ Neural verification failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing neural verification: {e}")

    # Test 2: Enhanced fact processing
    print("\n2. Testing Enhanced Fact Processing...")
    test_fact_processing = {
        "content": "Scientists discovered a new species of deep-sea creatures in the Mariana Trench.",
        "sources": [{"domain": "nature.com"}],
        "metadata": {"category": "science", "topic": "marine biology"},
    }

    try:
        response = requests.post(
            f"{base_url}/neural/process_fact", json=test_fact_processing,
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ Enhanced fact processing endpoint working!")
            print(f"   Status: {result['processing_result']['status']}")
            print(
                f"   Neural Confidence: {result['processing_result']['neural_verification']['confidence']:.3f}",
            )
        else:
            print(
                f"❌ Enhanced fact processing failed: {response.status_code}",
            )
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing enhanced fact processing: {e}")

    # Test 3: Dispute creation
    print("\n3. Testing Dispute Creation...")
    test_dispute = {
        "fact_id": "test_fact_123",
        "reason": "This fact appears to be based on unreliable sources.",
        "evidence": [
            {
                "node_id": "test_node",
                "evidence_type": "source_analysis",
                "evidence_content": "The source has a history of publishing false information.",
                "confidence_score": 0.9,
            },
        ],
    }

    try:
        response = requests.post(
            f"{base_url}/dispute/create", json=test_dispute,
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ Dispute creation endpoint working!")
            print(f"   Dispute ID: {result['dispute_id']}")
            return result["dispute_id"]  # Return for voting test
        print(f"❌ Dispute creation failed: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing dispute creation: {e}")

    return None


def test_dispute_voting(dispute_id):
    """Test dispute voting functionality."""
    if not dispute_id:
        return

    base_url = "http://127.0.0.1:8001"

    print("\n4. Testing Dispute Voting...")

    # Test voting on the dispute
    test_vote = {
        "dispute_id": dispute_id,
        "vote": True,  # Vote that fact is false
        "reasoning": "The sources are unreliable and lack proper citations.",
        "confidence": 0.8,
    }

    try:
        response = requests.post(f"{base_url}/dispute/vote", json=test_vote)
        if response.status_code == 200:
            result = response.json()
            print("✅ Dispute voting endpoint working!")
            print(f"   Status: {result['status']}")
            print(f"   Message: {result['message']}")
        else:
            print(f"❌ Dispute voting failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing dispute voting: {e}")


def test_status_endpoints():
    """Test status and performance endpoints."""
    base_url = "http://127.0.0.1:8001"

    print("\n5. Testing Status Endpoints...")

    # Test dispute status
    try:
        response = requests.get(f"{base_url}/dispute/status")
        if response.status_code == 200:
            result = response.json()
            print("✅ Dispute status endpoint working!")
            print(
                f"   Total disputes: {result['statistics']['total_disputes']}",
            )
            print(f"   Open disputes: {result['statistics']['open_disputes']}")
        else:
            print(f"❌ Dispute status failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing dispute status: {e}")

    # Test neural performance
    try:
        response = requests.get(f"{base_url}/neural/performance")
        if response.status_code == 200:
            result = response.json()
            print("✅ Neural performance endpoint working!")
            print(f"   Neural metrics: {result['neural_metrics']['status']}")
        else:
            print(f"❌ Neural performance failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing neural performance: {e}")


def main():
    """Main test function."""
    print("🚀 Starting Neural Network Node Tests")
    print("Make sure the Axiom node is running on port 8001")
    print("=" * 60)

    # Wait a moment for the node to be ready
    print("Waiting 3 seconds for node to be ready...")
    time.sleep(3)

    # Test neural endpoints
    dispute_id = test_neural_endpoints()

    # Test dispute voting
    test_dispute_voting(dispute_id)

    # Test status endpoints
    test_status_endpoints()

    print("\n" + "=" * 60)
    print("🎉 Neural Network Node Tests Completed!")
    print(
        "If you see ✅ marks, the neural network system is working in the node!",
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
