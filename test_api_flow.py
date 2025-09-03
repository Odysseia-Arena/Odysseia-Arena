#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整的API流程测试脚本 (v3)

该脚本模拟一个用户的完整交互流程，并测试所有主要的API端点。
"""

import requests
import uuid
import time
import json
import os

# --- 配置 ---
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
SESSION_ID = f"test_session_{uuid.uuid4()}"
DISCORD_ID = f"test_user_{uuid.uuid4()}"
BATTLE_TYPE = "high_tier"

# 全局变量，用于在测试函数之间传递状态
battle_id_store = {}
model_info_store = {}
character_messages_store = []


def print_step(title):
    """打印步骤标题"""
    print("\n" + "="*15 + f" {title} " + "="*15)

def print_request(method, url, body=None):
    """打印请求信息"""
    print(f"\n--> {method} {url}")
    if body:
        print("    Request Body:")
        print(json.dumps(body, indent=2, ensure_ascii=False))

def print_response(response):
    """打印并返回响应信息"""
    print(f"<-- Status Code: {response.status_code}")
    try:
        response_json = response.json()
        print("    Response Body:")
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
        return response_json
    except json.JSONDecodeError:
        print("    Response Body (non-JSON):")
        print(response.text)
        return None

def test_health_check():
    """测试 /health 端点"""
    print_step("Test: /health")
    url = f"{BASE_URL}/health"
    print_request("GET", url)
    response = requests.get(url)
    data = print_response(response)
    
    assert response.status_code == 200
    assert data and data.get("status") == "ok"
    assert "models_count" in data
    print("[SUCCESS] Health check passed.")

def test_leaderboard():
    """测试 /leaderboard 端点"""
    print_step("Test: /leaderboard")
    url = f"{BASE_URL}/leaderboard"
    print_request("GET", url)
    response = requests.get(url)
    data = print_response(response)

    assert response.status_code == 200
    assert data and "leaderboard" in data and "next_update_time" in data
    if data.get("leaderboard"):
        first_entry = data["leaderboard"][0]
        assert "rank" in first_entry
        assert "model_name" in first_entry
        assert "rating" in first_entry
    print("[SUCCESS] Leaderboard loaded.")

def test_start_battle_and_get_characters():
    """测试开始新对战并获取角色消息"""
    print_step("Test: POST /battle (start session)")
    url = f"{BASE_URL}/battle"
    payload = {
        "session_id": SESSION_ID,
        "battle_type": BATTLE_TYPE,
        "discord_id": DISCORD_ID,
        "input": None
    }
    print_request("POST", url, payload)
    response = requests.post(url, json=payload)
    data = print_response(response)

    assert response.status_code == 201
    assert data and "character_messages" in data
    assert data.get("status") == "pending_character_selection"
    character_messages = data.get("character_messages", [])
    assert len(character_messages) > 0
    character_messages_store.extend(character_messages)
    print("[SUCCESS] Started battle, got character messages.")

def test_character_selection():
    """测试选择角色消息"""
    print_step("Test: POST /character_selection")
    url = f"{BASE_URL}/character_selection"
    payload = {
        "session_id": SESSION_ID,
        "character_messages_id": 0
    }
    print_request("POST", url, payload)
    response = requests.post(url, json=payload)
    data = print_response(response)

    assert response.status_code == 200
    assert data and data.get("status") == "success"
    assert data.get("context_updated") is True
    assert "generated_options" in data
    print("[SUCCESS] Character selected.")

def test_continue_battle_first_turn():
    """测试继续对战的第一个回合"""
    print_step("Test: POST /battle (first turn)")
    url = f"{BASE_URL}/battle"
    user_input = character_messages_store[0]["options"][0] if character_messages_store[0].get("options") else "继续故事"
    payload = {
        "session_id": SESSION_ID,
        "battle_type": BATTLE_TYPE,
        "discord_id": DISCORD_ID,
        "input": user_input
    }
    print_request("POST", url, payload)
    response = requests.post(url, json=payload)
    data = print_response(response)

    assert response.status_code == 201
    assert data and "battle_id" in data
    assert "response_a" in data and "response_b" in data
    assert "text" in data["response_a"] and "options" in data["response_a"]
    battle_id_store["turn_1"] = data["battle_id"]
    print(f"[SUCCESS] First turn of battle created with ID: {data['battle_id']}")

def test_vote_and_reveal():
    """测试投票、获取对战详情和揭示模型"""
    battle_id = battle_id_store.get("turn_1")
    assert battle_id, "Battle ID from turn 1 not found."

    # --- Vote ---
    print_step("Test: POST /vote/{battle_id}")
    url = f"{BASE_URL}/vote/{battle_id}"
    payload = {"vote_choice": "model_a", "discord_id": DISCORD_ID}
    print_request("POST", url, payload)
    response = requests.post(url, json=payload)
    data = print_response(response)
    assert response.status_code == 200
    assert data and data.get("status") == "success"
    print("[SUCCESS] Voted successfully.")

    # --- Get Battle Details (Before Reveal) ---
    print_step("Test: GET /battle/{battle_id} (before reveal)")
    url = f"{BASE_URL}/battle/{battle_id}"
    print_request("GET", url)
    response = requests.get(url)
    data = print_response(response)
    assert response.status_code == 200
    assert data and data.get("status") == "completed"
    assert "model_a" not in data # Should be blind
    print("[SUCCESS] Got battle details before reveal.")

    # --- Reveal ---
    print_step("Test: POST /reveal/{battle_id}")
    url = f"{BASE_URL}/reveal/{battle_id}"
    print_request("POST", url)
    response = requests.post(url)
    data = print_response(response)
    assert response.status_code == 200
    assert data and "model_a_name" in data and "model_b_name" in data
    model_info_store["turn_1"] = data
    print("[SUCCESS] Revealed models.")

    # --- Get Battle Details (After Reveal) ---
    print_step("Test: GET /battle/{battle_id} (after reveal)")
    url = f"{BASE_URL}/battle/{battle_id}"
    print_request("GET", url)
    response = requests.get(url)
    data = print_response(response)
    assert response.status_code == 200
    assert data and data.get("revealed")
    assert "model_a" in data
    print("[SUCCESS] Got battle details after reveal.")
    
def test_other_vote_options():
    """测试 'tie' 和 'skip' 投票选项"""
    # 需要一个新的 battle
    print_step("Test: Other Vote Options ('tie', 'skip')")
    
    # 1. Create a new battle
    url = f"{BASE_URL}/battle"
    payload = {"session_id": SESSION_ID, "battle_type": BATTLE_TYPE, "input": "再来一次"}
    response = requests.post(url, json=payload)
    data = response.json()
    battle_id_tie = data.get("battle_id")
    assert battle_id_tie, "Failed to create battle for 'tie' vote test."
    print(f"Created new battle for 'tie' test: {battle_id_tie}")

    # 2. Test 'tie' vote
    url_vote_tie = f"{BASE_URL}/vote/{battle_id_tie}"
    payload_tie = {"vote_choice": "tie", "discord_id": DISCORD_ID}
    response_tie = requests.post(url_vote_tie, json=payload_tie)
    data_tie = print_response(response_tie)
    assert response_tie.status_code == 200
    assert data_tie.get("winner") == "tie"
    print("[SUCCESS] 'tie' vote successful.")

    # 3. Create another battle for 'skip'
    payload = {"session_id": SESSION_ID, "battle_type": BATTLE_TYPE, "input": "最后一次"}
    response = requests.post(url, json=payload)
    data = response.json()
    battle_id_skip = data.get("battle_id")
    assert battle_id_skip, "Failed to create battle for 'skip' vote test."
    print(f"Created new battle for 'skip' test: {battle_id_skip}")

    # 4. Test 'skip' vote
    url_vote_skip = f"{BASE_URL}/vote/{battle_id_skip}"
    payload_skip = {"vote_choice": "skip", "discord_id": DISCORD_ID}
    response_skip = requests.post(url_vote_skip, json=payload_skip)
    data_skip = print_response(response_skip)
    assert response_skip.status_code == 200
    assert data_skip.get("winner") == "skip"
    print("[SUCCESS] 'skip' vote successful.")

def test_get_latest_session():
    """测试 /sessions/latest 端点"""
    print_step("Test: POST /sessions/latest")
    url = f"{BASE_URL}/sessions/latest"
    payload = {"discord_id": DISCORD_ID}
    print_request("POST", url, payload)
    response = requests.post(url, json=payload)
    data = print_response(response)

    assert response.status_code == 200
    assert data and data.get("session_id") == SESSION_ID
    print("[SUCCESS] Got latest session ID.")

def test_generate_options():
    """测试 /generate_options 端点"""
    print_step("Test: POST /generate_options")
    url = f"{BASE_URL}/generate_options"
    payload = {"session_id": SESSION_ID}
    print_request("POST", url, payload)
    response = requests.post(url, json=payload)
    data = print_response(response)

    assert response.status_code == 200
    assert data and "generated_options" in data
    assert len(data["generated_options"]) > 0
    print("[SUCCESS] Generated new options.")

def test_battle_statistics():
    """测试 /api/battle_statistics 端点"""
    print_step("Test: GET /api/battle_statistics")
    url = f"{BASE_URL}/api/battle_statistics"
    print_request("GET", url)
    response = requests.get(url)
    data = print_response(response)

    assert response.status_code == 200
    assert data and "win_rate_matrix" in data and "match_count_matrix" in data
    print("[SUCCESS] Battle statistics loaded.")

def test_prompt_statistics():
    """测试 /api/prompt_statistics 端点"""
    print_step("Test: GET /api/prompt_statistics")
    url = f"{BASE_URL}/api/prompt_statistics"
    print_request("GET", url)
    response = requests.get(url)
    data = print_response(response)

    assert response.status_code == 200
    assert data and "prompt_statistics" in data
    print("[SUCCESS] Prompt statistics loaded.")

def test_battleback_and_unstuck():
    """测试 /battleback 和 /battleunstuck 端点"""
    # /battleback is hard to test deterministically without a pending battle.
    # We will just call it and check for a valid response (either data or 'not found').
    print_step("Test: POST /battleback")
    url_back = f"{BASE_URL}/battleback"
    payload = {"discord_id": DISCORD_ID}
    print_request("POST", url_back, payload)
    response = requests.post(url_back, json=payload)
    data = print_response(response)
    assert response.status_code in [200, 404]
    print("[SUCCESS] /battleback responded as expected.")

    # /battleunstuck should always succeed.
    print_step("Test: POST /battleunstuck")
    url_unstuck = f"{BASE_URL}/battleunstuck"
    print_request("POST", url_unstuck, payload)
    response = requests.post(url_unstuck, json=payload)
    data = print_response(response)
    assert response.status_code == 200
    assert "message" in data
    print("[SUCCESS] /battleunstuck responded successfully.")


def main():
    """主执行函数"""
    try:
        test_health_check()
        test_leaderboard()
        test_start_battle_and_get_characters()
        test_character_selection()
        test_continue_battle_first_turn()
        test_vote_and_reveal()
        test_other_vote_options()
        test_get_latest_session()
        test_generate_options()
        test_battle_statistics()
        test_prompt_statistics()
        test_battleback_and_unstuck()
        
        print("\n\n" + "*"*20 + " ALL TESTS PASSED " + "*"*20)

    except AssertionError as e:
        print(f"\n\n[!!!] TEST FAILED: {e}")
    except Exception as e:
        print(f"\n\n[!!!] AN UNEXPECTED ERROR OCCURRED: {e}")

if __name__ == "__main__":
    main()