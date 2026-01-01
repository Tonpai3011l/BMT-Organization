import discord
import os
import json
from discord.ext import commands
from discord import app_commands, ui
from dotenv import load_dotenv

from keep_alive import server_on


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

class NameModal(ui.Modal, title='กรุณาใส่ชื่อของคุณ'):
    name_input = ui.TextInput(
        label='ชื่อ',
        placeholder='ใส่ชื่อที่นี่...',
        min_length=1,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        log_channel_id = config.get('log_channel_id')
        verify_role_id = config.get('verify_role_id')
        
        role_status = "ไม่ได้ตั้งค่าระบบยศ"
        if verify_role_id:
            role = interaction.guild.get_role(int(verify_role_id))
            if role:
                try:
                    await interaction.user.add_roles(role)
                    role_status = f"เพิ่มยศ {role.name} สำเร็จ"
                except Exception:
                    role_status = f"เพิ่มยศไม่สำเร็จ (ขาดสิทธิ์)"
            else:
                role_status = "ไม่พบยศที่ตั้งค่าไว้"

        if log_channel_id:
            log_channel = interaction.client.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="บันทึกข้อมูลและปรับปรุงสถานะ", color=discord.Color.green())
                embed.add_field(name="ชื่อที่กรอก", value=self.name_input.value, inline=False)
                embed.add_field(name="ผู้ใช้", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                embed.add_field(name="สถานะยศ", value=role_status, inline=True)
                await log_channel.send(embed=embed)

        await interaction.response.send_message(f"ลงทะเบียนสำเร็จ! (ชื่อ: {self.name_input.value}, {role_status})", ephemeral=True)



class SetupView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='ลงทะเบียน', style=discord.ButtonStyle.primary, custom_id='setup_name_button')
    async def name_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(NameModal())

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='.',
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        self.add_view(SetupView()) # Persistent view
        await self.tree.sync()
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("Command tree synced.")
        print("------")

    async def on_ready(self):
        pass

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.user.id:
            return

        config = load_config()
        if payload.message_id != config.get('rolegiver_message_id'):
            return

        roles_mapping = config.get('rolegiver_roles', {})
        emoji_str = str(payload.emoji)
        
        if emoji_str in roles_mapping:
            guild = self.get_guild(payload.guild_id)
            if not guild: return
            
            role = guild.get_role(int(roles_mapping[emoji_str]))
            if not role: return
            
            member = guild.get_member(payload.user_id)
            if not member: return
            
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print(f"Failed to add role {role.name} to {member.name} (Forbidden)")

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        config = load_config()
        if payload.message_id != config.get('rolegiver_message_id'):
            return

        roles_mapping = config.get('rolegiver_roles', {})
        emoji_str = str(payload.emoji)
        
        if emoji_str in roles_mapping:
            guild = self.get_guild(payload.guild_id)
            if not guild: return
            
            role = guild.get_role(int(roles_mapping[emoji_str]))
            if not role: return
            
            member = guild.get_member(payload.user_id)
            if not member: return
            
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                print(f"Failed to remove role {role.name} from {member.name} (Forbidden)")


bot = MyBot()

@bot.tree.command(name="setup", description="ส่งปุ่มลงทะเบียนไปยังห้องที่กำหนด")
@app_commands.describe(channel="ห้องที่ต้องการส่งปุ่ม")
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="ระบบลงทะเบียน",
        description="คลิกปุ่มด้านล่างเพื่อใส่ชื่อของคุณ",
        color=discord.Color.blue()
    )
    await channel.send(embed=embed, view=SetupView())
    await interaction.response.send_message(f"ส่งปุ่มไปที่ {channel.mention} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="setlogs", description="ตั้งค่าห้องสำหรับบันทึก Log")
@app_commands.describe(channel="ห้องที่ต้องการใช้บันทึก Log")
async def setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config['log_channel_id'] = channel.id
    save_config(config)
    await interaction.response.send_message(f"ตั้งค่า Log Channel เป็น {channel.mention} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="set_verify_role", description="ตั้งค่ายศที่จะได้รับเมื่อลงทะเบียนสำเร็จ")
@app_commands.describe(role="ยศที่ต้องการมอบให้")
async def set_verify_role(interaction: discord.Interaction, role: discord.Role):
    config = load_config()
    config['verify_role_id'] = role.id
    save_config(config)
    await interaction.response.send_message(f"ตั้งค่ายศเป็น {role.mention} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="setup_rolegiver", description="ส่ง Embed สำหรับเลือกยศ (Role Giver)")
@app_commands.describe(channel="ห้องที่ต้องการให้ส่ง Embed เลือกยศ")
async def setup_rolegiver(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="เลือกยศที่ต้องการ",
        description="คลิกเลือก Emoji ด้านล่างเพื่อรับยศที่คุณต้องการ",
        color=discord.Color.orange()
    )
    msg = await channel.send(embed=embed)
    
    config = load_config()
    config['rolegiver_message_id'] = msg.id
    config['rolegiver_channel_id'] = channel.id
    if 'rolegiver_roles' not in config:
        config['rolegiver_roles'] = {}
    save_config(config)
    
    await interaction.response.send_message(f"สร้างระบบให้ยศใน {channel.mention} เรียบร้อยแล้ว (ID: {msg.id})", ephemeral=True)

@bot.tree.command(name="add", description="เพิ่ม Emoji และ Role สำหรับระบบเลือกยศ")
@app_commands.describe(emoji="Emoji ที่ต้องการใช้", role="ยศที่ต้องการมอบให้")
async def add_role_giver(interaction: discord.Interaction, emoji: str, role: discord.Role):
    config = load_config()
    msg_id = config.get('rolegiver_message_id')
    channel_id = config.get('rolegiver_channel_id')
    
    if not msg_id or not channel_id:
        return await interaction.response.send_message("กรุณาใช้คำสั่ง /setup_rolegiver ก่อน", ephemeral=True)
    
    channel = bot.get_channel(channel_id)
    if not channel:
        return await interaction.response.send_message("ไม่พบห้องที่ตั้งค่าไว้", ephemeral=True)
    
    try:
        msg = await channel.fetch_message(msg_id)
    except Exception:
        return await interaction.response.send_message("ไม่พบข้อความเลือกยศ (อาจถูกลบไปแล้ว)", ephemeral=True)
    
    try:
        await msg.add_reaction(emoji)
    except Exception:
        return await interaction.response.send_message("ไม่สามารถเพิ่ม Emoji นี้ได้ (บอทอาจไม่มีสิทธิ์หรือ Emoji ไม่ถูกต้อง)", ephemeral=True)
    
    if 'rolegiver_roles' not in config:
        config['rolegiver_roles'] = {}
    
    config['rolegiver_roles'][emoji] = role.id
    save_config(config)
    
    await interaction.response.send_message(f"เพิ่ม Emoji {emoji} สำหรับยศ {role.name} เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="remove", description="ลบ Emoji และ Role ออกจากระบบเลือกยศ")
@app_commands.describe(emoji="Emoji ที่ต้องการลบออก")
async def remove_role_giver(interaction: discord.Interaction, emoji: str):
    config = load_config()
    roles_mapping = config.get('rolegiver_roles', {})
    
    if emoji not in roles_mapping:
        return await interaction.response.send_message("ไม่มีการตั้งค่า Emoji นี้ไว้ในระบบ", ephemeral=True)
    
    del roles_mapping[emoji]
    save_config(config)
    
    # Try to remove reaction from message
    msg_id = config.get('rolegiver_message_id')
    channel_id = config.get('rolegiver_channel_id')
    if msg_id and channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.clear_reaction(emoji)
            except Exception:
                pass # Ignore if fail to clear reaction
    
    await interaction.response.send_message(f"ลบ Emoji {emoji} ออกจากระบบเรียบร้อยแล้ว", ephemeral=True)


server_on()

if __name__ == "__main__":

    try:
        if TOKEN:
            bot.run(TOKEN)
        else:
            print("Error: DISCORD_TOKEN not found in .env file.")
    except Exception as e:
        print(f"Error: {e}")
