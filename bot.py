#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC28 Telegram机器人 - 卡密激活版
部署到Render.com，24小时运行，无需挂机
"""

import os
import json
import time
import random
import string
import hashlib
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
from telethon import TelegramClient, events, Button

# ============================================================
# 配置（部署到Render时用环境变量）
# ============================================================
API_ID = int(os.environ.get('API_ID', '123456'))  # 从 https://my.telegram.org 获取
API_HASH = os.environ.get('API_HASH', 'your_api_hash')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7123456789:AAFxxxxxxxxxxxxx')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '123456789'))  # 你的Telegram用户ID

# 数据API
DATA_API_URL = 'https://super.pc28998.com/history/JND28'
CHECK_INTERVAL = 15  # 检测间隔秒数

# ============================================================
# 卡密系统
# ============================================================

class CardSystem:
    """卡密管理"""
    
    def __init__(self):
        self.cards_file = 'cards.json'
        self.users_file = 'users.json'
        self.cards = self.load_cards()
        self.users = self.load_users()
    
    def load_cards(self):
        if os.path.exists(self.cards_file):
            with open(self.cards_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_cards(self):
        with open(self.cards_file, 'w') as f:
            json.dump(self.cards, f, indent=2)
    
    def load_users(self):
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def generate_cards(self, count: int, days: int, prefix: str = 'PC28') -> List[str]:
        """生成卡密"""
        new_cards = []
        for _ in range(count):
            code = f"{prefix}-{self._random_str(4)}-{self._random_str(4)}-{self._random_str(4)}"
            self.cards[code] = {
                'days': days,
                'used': False,
                'used_by': None,
                'used_at': None,
                'created': datetime.now().isoformat()
            }
            new_cards.append(code)
        self.save_cards()
        return new_cards
    
    def _random_str(self, length: int) -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    def activate(self, user_id: int, card_code: str) -> Tuple[bool, str]:
        """激活卡密"""
        card_code = card_code.strip().upper()
        
        if card_code not in self.cards:
            return False, "❌ 卡密无效，请检查后重试"
        
        card = self.cards[card_code]
        if card['used']:
            return False, f"❌ 该卡密已被使用（{card['used_at']}）"
        
        # 计算到期时间
        expire_date = datetime.now() + timedelta(days=card['days'])
        
        # 标记卡密已使用
        card['used'] = True
        card['used_by'] = user_id
        card['used_at'] = datetime.now().isoformat()
        
        # 更新用户信息
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                'activated': False,
                'expire_date': None,
                'history': []
            }
        
        user = self.users[user_id_str]
        if user['activated'] and user['expire_date']:
            old_expire = datetime.fromisoformat(user['expire_date'])
            if old_expire > datetime.now():
                # 累加天数
                expire_date = old_expire + timedelta(days=card['days'])
        
        user['activated'] = True
        user['expire_date'] = expire_date.isoformat()
        user['history'].append({
            'card': card_code,
            'days': card['days'],
            'activated_at': datetime.now().isoformat()
        })
        
        self.save_cards()
        self.save_users()
        
        return True, f"✅ 激活成功！到期时间：{expire_date.strftime('%Y-%m-%d %H:%M')}（{card['days']}天）"
    
    def check_user(self, user_id: int) -> Tuple[bool, str]:
        """检查用户是否已激活"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            return False, "❌ 您还未激活，请使用 /activate 卡密 激活"
        
        user = self.users[user_id_str]
        if not user['activated']:
            return False, "❌ 您还未激活"
        
        if user['expire_date']:
            expire = datetime.fromisoformat(user['expire_date'])
            if expire < datetime.now():
                return False, f"❌ 已过期（{expire.strftime('%Y-%m-%d')}），请续费"
            
            remaining = expire - datetime.now()
            days = remaining.days
            hours = remaining.seconds // 3600
            return True, f"✅ 有效期至 {expire.strftime('%Y-%m-%d %H:%M')}（剩余{days}天{hours}小时）"
        
        return False, "❌ 状态异常"
    
    def get_all_users(self) -> List[Dict]:
        """获取所有激活用户"""
        active_users = []
        for uid, info in self.users.items():
            if info['activated'] and info['expire_date']:
                expire = datetime.fromisoformat(info['expire_date'])
                remaining = (expire - datetime.now()).days
                active_users.append({
                    'user_id': int(uid),
                    'expire_date': info['expire_date'],
                    'remaining_days': remaining,
                    'is_active': expire > datetime.now()
                })
        return active_users


# ============================================================
# 预测算法
# ============================================================

class PC28Predictor:
    """PC28预测器"""
    
    def __init__(self, history: List[Dict]):
        self.history = history
    
    def predict(self) -> Optional[Dict]:
        if len(self.history) < 10:
            return None
        
        kill_group = self._xiaodun_5y_kill()
        if not kill_group:
            return None
        
        all_groups = ['小单', '小双', '大单', '大双']
        remaining = [g for g in all_groups if g != kill_group]
        recent20 = self.history[-20:]
        combo_counts = Counter(d['combination'] for d in recent20)
        double_group = sorted(remaining, key=lambda x: combo_counts.get(x, 0), reverse=True)[:2]
        main_attack = list(double_group)
        
        recent50 = self.history[-50:]
        total_freq = Counter(d['total'] for d in recent50)
        
        main_codes = {}
        for combo in main_attack:
            valid = []
            for t in range(28):
                is_big = t >= 14
                is_single = t % 2 == 1
                zuhe = ('大' if is_big else '小') + ('单' if is_single else '双')
                if zuhe == combo:
                    valid.append((t, total_freq.get(t, 0)))
            valid.sort(key=lambda x: x[1], reverse=True)
            main_codes[combo] = [v[0] for v in valid[:2]]
        
        all_valid = []
        for t in range(28):
            is_big = t >= 14
            is_single = t % 2 == 1
            zuhe = ('大' if is_big else '小') + ('单' if is_single else '双')
            if zuhe in main_attack:
                all_valid.append((t, total_freq.get(t, 0)))
        all_valid.sort(key=lambda x: x[1], reverse=True)
        codes = [v[0] for v in all_valid[:4]]
        
        latest = self.history[-1]
        next_period = str(int(latest['expect']) + 1)
        short_period = next_period[-2:]
        
        return {
            'short_period': short_period,
            'next_period': next_period,
            'kill_group': kill_group,
            'double_group': double_group,
            'main_attack': main_attack,
            'main_codes': main_codes,
            'codes': codes,
            'latest': latest
        }
    
    def _xiaodun_5y_kill(self) -> Optional[str]:
        latest = self.history[-1]
        current_yu5 = latest['yu5']
        current_nums = list(latest['nums'])
        
        position_rules = {0: 'shi', 1: 'ge', 2: 'bai', 3: 'bai_shi', 4: 'ge'}
        yu5_to_kill = {0: '小单', 1: '大单', 2: '小双', 3: '大双', 4: '小单'}
        
        ref_periods = [d for d in self.history[:-1] if d['yu5'] == current_yu5]
        ref_periods = ref_periods[-4:] if len(ref_periods) >= 4 else ref_periods
        if not ref_periods:
            ref_periods = self.history[-6:-1]
        
        position_rule = position_rules.get(current_yu5, 'ge')
        kill_groups = []
        
        for ref in ref_periods:
            ref_nums = list(ref['nums'])
            new_nums = current_nums.copy()
            
            if position_rule == 'bai':
                new_nums[0] = (current_nums[0] + ref_nums[0]) % 10
            elif position_rule == 'shi':
                new_nums[1] = (current_nums[1] + ref_nums[1]) % 10
            elif position_rule == 'ge':
                new_nums[2] = (current_nums[2] + ref_nums[2]) % 10
            elif position_rule == 'bai_shi':
                new_num = (current_nums[0] + current_nums[1] + ref_nums[0] + ref_nums[1]) % 10
                new_nums[0] = new_num
                new_nums[1] = new_num
            
            new_total = sum(new_nums)
            new_yu5 = new_total % 5
            kill_groups.append(yu5_to_kill.get(new_yu5, '小单'))
        
        weights = [0.4, 0.3, 0.2, 0.1][:len(kill_groups)]
        scores = {}
        for kg, w in zip(kill_groups, weights):
            scores[kg] = scores.get(kg, 0) + w
        
        if not scores:
            return None
        
        final_kill = max(scores, key=scores.get)
        winners = [k for k, v in scores.items() if v == scores[final_kill]]
        if len(winners) > 1:
            recent = self.history[-20:]
            combo_counts = Counter(d['combination'] for d in recent)
            final_kill = min(winners, key=lambda x: combo_counts.get(x, 0))
        
        return final_kill


# ============================================================
# 数据管理
# ============================================================

class DataManager:
    """数据管理"""
    
    def __init__(self):
        self.data_file = 'pc28_data.json'
        self.data = self.load()
    
    def load(self) -> List[Dict]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def save(self):
        if len(self.data) > 500:
            self.data = self.data[-500:]
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def fetch_and_update(self) -> int:
        """从API获取并更新数据，返回新增数量"""
        try:
            resp = requests.get(DATA_API_URL, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Referer': 'https://super.pc28998.com/'
            }, timeout=15)
            data = resp.json()
            
            if data.get('code') != 1 or 'data' not in data:
                return 0
            
            existing = {d['expect'] for d in self.data}
            added = 0
            
            for item in data['data']:
                if item['expect'] not in existing:
                    parts = item['opencode'].split(',')
                    if len(parts) == 3:
                        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                        total = a + b + c
                        self.data.append({
                            'expect': item['expect'],
                            'nums': [a, b, c],
                            'total': total,
                            'combination': ('大' if total >= 14 else '小') + ('单' if total % 2 == 1 else '双'),
                            'is_big': total >= 14,
                            'is_single': total % 2 == 1,
                            'yu5': total % 5
                        })
                        existing.add(item['expect'])
                        added += 1
            
            if added > 0:
                self.data.sort(key=lambda x: int(x['expect']))
                self.save()
            
            return added
        except Exception as e:
            print(f"数据获取失败: {e}")
            return 0


# ============================================================
# 格式化输出
# ============================================================

def format_prediction(result: Dict) -> str:
    """格式化预测结果"""
    period = result['short_period']
    kill = result['kill_group']
    doub = ''.join(result['double_group'])
    codes = '/'.join(f"{c:02d}" for c in result['codes'])
    
    text = f"🎯 **{period}.杀{kill} {doub} {codes}**\n\n"
    text += f"📊 预测期号：{result['next_period']}期\n"
    text += f"🔴 杀组：{kill}\n"
    text += f"🟢 双组：{' '.join(result['double_group'])}\n"
    text += f"💎 特码：{'/'.join(f'{c:02d}' for c in result['codes'])}\n\n"
    text += f"🔥 主攻组合：\n"
    for combo in result['main_attack']:
        codes_str = '/'.join(f"{c:02d}" for c in result['main_codes'].get(combo, []))
        text += f"   • {combo}：{codes_str}\n"
    
    text += f"\n📅 基于最新期：{result['latest']['expect']}期 "
    text += f"{'+'.join(map(str, result['latest']['nums']))}={result['latest']['total']} "
    text += f"{result['latest']['combination']}"
    
    return text


# ============================================================
# Telegram机器人
# ============================================================

card_system = CardSystem()
data_manager = DataManager()
monitor_users = set()  # 订阅自动推送的用户

# 创建机器人客户端
bot = TelegramClient('pc28_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)


def require_activation(func):
    """装饰器：检查用户是否激活"""
    async def wrapper(event):
        user_id = event.sender_id
        is_valid, msg = card_system.check_user(user_id)
        if not is_valid:
            await event.respond(msg)
            return
        await func(event)
    return wrapper


# ============================================================
# 命令处理
# ============================================================

@bot.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    """开始"""
    user_id = event.sender_id
    is_valid, msg = card_system.check_user(user_id)
    
    text = "🤖 **PC28预测机器人**\n\n"
    text += "📋 命令列表：\n"
    text += "/activate 卡密 - 激活机器人\n"
    text += "/predict - 手动预测\n"
    text += "/status - 查看状态\n"
    text += "/sub - 订阅自动推送\n"
    text += "/unsub - 取消订阅\n"
    text += "/help - 帮助\n\n"
    
    if is_valid:
        text += f"✅ {msg}\n"
    else:
        text += f"{msg}\n"
    
    await event.respond(text)


@bot.on(events.NewMessage(pattern='/activate'))
async def cmd_activate(event):
    """激活卡密"""
    parts = event.text.split()
    if len(parts) < 2:
        await event.respond("使用方法：/activate PC28-XXXX-XXXX-XXXX")
        return
    
    card_code = parts[1]
    user_id = event.sender_id
    
    success, msg = card_system.activate(user_id, card_code)
    await event.respond(msg)


@bot.on(events.NewMessage(pattern='/predict'))
@require_activation
async def cmd_predict(event):
    """手动预测"""
    if len(data_manager.data) < 10:
        await event.respond(f"⚠️ 数据不足（当前{len(data_manager.data)}期），请等待数据更新...")
        return
    
    predictor = PC28Predictor(data_manager.data)
    result = predictor.predict()
    
    if result:
        text = format_prediction(result)
        await event.respond(text, parse_mode='markdown')
    else:
        await event.respond("❌ 预测失败，数据不足")


@bot.on(events.NewMessage(pattern='/status'))
@require_activation
async def cmd_status(event):
    """查看状态"""
    user_id = event.sender_id
    is_valid, msg = card_system.check_user(user_id)
    
    text = f"📊 **系统状态**\n\n"
    text += f"💾 数据量：{len(data_manager.data)} 条\n"
    text += f"🤖 订阅用户：{len(monitor_users)} 人\n"
    
    if data_manager.data:
        latest = data_manager.data[-1]
        text += f"📅 最新期：{latest['expect']}\n"
        text += f"🔢 号码：{'+'.join(map(str, latest['nums']))}={latest['total']}\n"
        text += f"🏷️ 组合：{latest['combination']}\n"
    
    text += f"\n{msg}"
    await event.respond(text)


@bot.on(events.NewMessage(pattern='/sub'))
@require_activation
async def cmd_sub(event):
    """订阅自动推送"""
    monitor_users.add(event.sender_id)
    await event.respond("✅ 已订阅自动推送，每期开奖后自动发送预测")


@bot.on(events.NewMessage(pattern='/unsub'))
async def cmd_unsub(event):
    """取消订阅"""
    monitor_users.discard(event.sender_id)
    await event.respond("✅ 已取消自动推送")


@bot.on(events.NewMessage(pattern='/help'))
async def cmd_help(event):
    """帮助"""
    text = "📋 **帮助**\n\n"
    text += "1️⃣ 首先使用 /activate 卡密 激活\n"
    text += "2️⃣ 激活后可使用 /predict 预测\n"
    text += "3️⃣ 使用 /sub 订阅自动推送\n"
    text += "4️⃣ 机器人会自动监控数据，推送预测结果\n\n"
    text += "📌 预测格式：期号.杀X组合 XX组合 特码\n"
    text += "   如：44.杀小单 小双大单 12/14/17/19\n\n"
    text += "🔑 获取卡密请联系管理员"
    await event.respond(text)


# ============================================================
# 管理员命令
# ============================================================

@bot.on(events.NewMessage(pattern='/admin'))
async def cmd_admin(event):
    """管理员面板"""
    if event.sender_id != ADMIN_ID:
        await event.respond("❌ 无权限")
        return
    
    text = "🔧 **管理员面板**\n\n"
    text += "/gencards 数量 天数 - 生成卡密\n"
    text += "/listusers - 查看激活用户\n"
    text += "/broadcast 消息 - 群发消息\n"
    await event.respond(text)


@bot.on(events.NewMessage(pattern='/gencards'))
async def cmd_gencards(event):
    """生成卡密"""
    if event.sender_id != ADMIN_ID:
        return
    
    parts = event.text.split()
    count = int(parts[1]) if len(parts) > 1 else 5
    days = int(parts[2]) if len(parts) > 2 else 30
    
    cards = card_system.generate_cards(count, days)
    text = f"✅ 已生成 {count} 张卡密（{days}天）：\n\n"
    text += '\n'.join(f"`{c}`" for c in cards)
    text += "\n\n可直接复制发送给用户"
    
    await event.respond(text, parse_mode='markdown')


@bot.on(events.NewMessage(pattern='/listusers'))
async def cmd_listusers(event):
    """查看用户"""
    if event.sender_id != ADMIN_ID:
        return
    
    users = card_system.get_all_users()
    if not users:
        await event.respond("暂无激活用户")
        return
    
    text = f"📊 **激活用户（{len(users)}人）**\n\n"
    for u in sorted(users, key=lambda x: x['remaining_days']):
        status = "✅" if u['is_active'] else "❌"
        text += f"{status} `{u['user_id']}` - 剩余{u['remaining_days']}天\n"
    
    await event.respond(text, parse_mode='markdown')


@bot.on(events.NewMessage(pattern='/broadcast'))
async def cmd_broadcast(event):
    """群发消息"""
    if event.sender_id != ADMIN_ID:
        return
    
    msg = event.text.replace('/broadcast', '').strip()
    if not msg:
        await event.respond("用法：/broadcast 消息内容")
        return
    
    users = card_system.get_all_users()
    success = 0
    for u in users:
        if u['is_active']:
            try:
                await bot.send_message(u['user_id'], f"📢 **管理员通知**\n\n{msg}", parse_mode='markdown')
                success += 1
            except:
                pass
    
    await event.respond(f"✅ 已发送给 {success}/{len(users)} 位活跃用户")


# ============================================================
# 自动监控循环
# ============================================================

async def monitor_loop():
    """自动监控数据更新并推送"""
    print("🔄 监控循环启动...")
    last_period = None
    
    # 首次加载数据
    data_manager.fetch_and_update()
    if data_manager.data:
        last_period = data_manager.data[-1]['expect']
    
    while True:
        try:
            added = data_manager.fetch_and_update()
            
            if added > 0 and data_manager.data:
                latest = data_manager.data[-1]
                new_period = latest['expect']
                
                if new_period != last_period:
                    print(f"📡 新数据: {new_period}")
                    last_period = new_period
                    
                    # 预测
                    if len(data_manager.data) >= 10:
                        predictor = PC28Predictor(data_manager.data)
                        result = predictor.predict()
                        
                        if result:
                            text = format_prediction(result)
                            text = f"🔔 **新一期开奖！**\n{latest['expect']}期 {'+'.join(map(str, latest['nums']))}={latest['total']} {latest['combination']}\n\n" + text
                            
                            # 推送给所有订阅用户
                            for user_id in list(monitor_users):
                                try:
                                    is_valid, _ = card_system.check_user(user_id)
                                    if is_valid:
                                        await bot.send_message(user_id, text, parse_mode='markdown')
                                except Exception as e:
                                    print(f"推送失败 {user_id}: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"监控错误: {e}")
            await asyncio.sleep(30)


# ============================================================
# 主程序
# ============================================================

import asyncio

async def main():
    print("🤖 PC28 Telegram机器人启动中...")
    print(f"📡 数据API: {DATA_API_URL}")
    
    # 启动监控任务
    asyncio.create_task(monitor_loop())
    
    # 启动机器人
    print("✅ 机器人已启动，等待消息...")
    await bot.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())