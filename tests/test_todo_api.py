#!/usr/bin/env python3
"""
Quick test script for Todo List API endpoints
Run this while the webui backend is running to verify functionality
"""

import requests
import json

BASE_URL = "http://localhost:5555"

def test_todos():
    """Test the todo list API endpoints"""
    print("🧪 Testing Todo List API Endpoints\n")
    
    # 1. Test GET (should be empty initially or have existing todos)
    print("1️⃣ Testing GET /api/todos")
    response = requests.get(f"{BASE_URL}/api/todos")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Success: {data.get('success')}")
    print(f"   Existing todos: {len(data.get('todos', []))}\n")
    
    # 2. Test POST (create a new todo)
    print("2️⃣ Testing POST /api/todos")
    new_todo_data = {"text": "Test improvement: Add dark mode toggle"}
    response = requests.post(f"{BASE_URL}/api/todos", json=new_todo_data)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Success: {data.get('success')}")
    
    if data.get('success'):
        todo_id = data['todo']['id']
        print(f"   Created todo ID: {todo_id}")
        print(f"   Text: {data['todo']['text']}\n")
        
        # 3. Test PUT (update the todo)
        print("3️⃣ Testing PUT /api/todos/<id> (toggle completed)")
        update_data = {"completed": True}
        response = requests.put(f"{BASE_URL}/api/todos/{todo_id}", json=update_data)
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Success: {data.get('success')}\n")
        
        # 4. Test DELETE
        print("4️⃣ Testing DELETE /api/todos/<id>")
        response = requests.delete(f"{BASE_URL}/api/todos/{todo_id}")
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Success: {data.get('success')}")
        print(f"   Remaining todos: {len(data.get('todos', []))}\n")
    
    print("✅ All tests completed!")

if __name__ == "__main__":
    try:
        test_todos()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to backend at http://localhost:5555")
        print("   Make sure the WebUI backend is running!")
    except Exception as e:
        print(f"❌ Test failed: {e}")




