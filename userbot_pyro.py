"""
pip install pyrogram tgcrypto
"""

import asyncio
import re
import os
from pyrogram import Client, filters, enums
from pyrogram.errors import UserAlreadyParticipant, FloodWait

# API Credentials
API_ID = 278xxxxx
API_HASH = 'dbb31988b20xxxxxxxxxxxxxxxxxxxx'
BOT_TOKEN = '8374477649:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

user_client = Client('anon_pyro', api_id=API_ID, api_hash=API_HASH)
bot_client = Client('bot_pyro', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

CC_PATTERN = r'\b(\d{15,16}\|\d{1,2}\|\d{2,4}\|\d{3,4})\b'
DEFAULT_KEYWORDS = ['charged']

def parse_arguments(text):
    text = re.sub(r'^/scr\s+', '', text)
    
    keywords = DEFAULT_KEYWORDS
    logic_mode = 'OR' 
    
    kw_match = re.search(r'\[(.*?)\]', text)
    if kw_match:
        kw_str = kw_match.group(1)
        
        if ',' in kw_str:
            logic_mode = 'AND'
            keywords = [k.strip().lower() for k in kw_str.split(',')]
        else:
            logic_mode = 'OR'
            keywords = [k.strip().lower() for k in kw_str.split('/')]
            
        text = text.replace(kw_match.group(0), '')
    
    parts = [p for p in text.split(' ') if p.strip()]
    
    if len(parts) < 2:
        return None, None, None, None
        
    try:
        limit = int(parts[-1])
        target = parts[0]
        
        if len(parts) == 3:
             additional_kw = parts[1]
             keywords = [additional_kw.strip().lower()]
             logic_mode = 'OR'

    except ValueError:
        return None, None, None, None
        
    return target, keywords, logic_mode, limit

@bot_client.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply(
        "👋 **Hello! I am your Scraper Bot (Pyrogram Edition).**\n\n"
        "**Available Commands:**\n"
        "1️⃣ **Standard Scrape:**\n"
        "`/scr <target> <amount>`\n"
        "(Uses default keywords: `charged`)\n\n"
        "2️⃣ **BIN/Keyword Scrape:**\n"
        "`/scr <target> <bin_or_keyword> <amount>`\n"
        "Example: `/scr @channel 424242 100`\n\n"
        "3️⃣ **Advanced Scrape (Multiple Keywords):**\n"
        "`/scr <target> [key1, key2] <amount>` (AND Logic)\n"
        "`/scr <target> [key1/key2] <amount>` (OR Logic)\n"
    )

@bot_client.on_message(filters.command("scr"))
async def scrape_command(client, message):
    target, keywords, logic_mode, target_amount = parse_arguments(message.text)
    
    if not target or not target_amount:
        await message.reply("❌ Invalid Format.\nUse: `/scr <target> [optional/keywords] <amount>`")
        return

    status_msg = await message.reply(
        f"⏳ **Processing...**\n"
        f"Target: `{target}`\n"
        f"Keywords: `{', '.join(keywords)}` ({logic_mode} logic)\n"
        f"Goal: `{target_amount}` cards"
    )

    try:
        chat_entity = None
        
        if "t.me/+" in target or "joinchat" in target:
            try:
                chat = await user_client.join_chat(target)
                chat_entity = chat
                await status_msg.edit(f"✅ Userbot joined **{chat.title}**!")
            except UserAlreadyParticipant:
                 try:
                     chat = await user_client.get_chat(target)
                     chat_entity = chat
                     await status_msg.edit(f"⚠️ Userbot already in **{chat.title}**.")
                 except Exception as e:
                     await status_msg.edit(f"❌ Userbot is in chat but couldn't resolve it: {e}")
                     return
            except Exception as e:
                await status_msg.edit(f"❌ Join Error: {e}")
                return
        else:
            try:
                chat_entity = await user_client.get_chat(target)
            except Exception as e:
                await status_msg.edit(f"❌ Could not find entity `{target}`: {e}")
                return

        await status_msg.edit(f"🔍 **Scraping {chat_entity.title}...**\nLooking for: {', '.join(keywords)}")

        count = 0
        scanned_count = 0
        keyword_match_count = 0
        scraped_data = []

        async for msg in user_client.get_chat_history(chat_entity.id):
            scanned_count += 1
            if scanned_count % 500 == 0:
                await status_msg.edit(
                    f"🔄 **Scanning...**\n"
                    f"Scanned: `{scanned_count}` messages\n"
                    f"Found: `{count}/{target_amount}` cards"
                )

            if msg.text or msg.caption:
                text = msg.text or msg.caption
                text_lower = text.lower()
                
                # Check for CCs
                cc_matches = list(re.finditer(CC_PATTERN, text))
                
                if not cc_matches:
                    continue
                    
                header_text = text[:cc_matches[0].start()].lower()

                for i, match in enumerate(cc_matches):
                    cc_details = match.group(1)
                    
                    start_pos = match.end()
                    end_pos = cc_matches[i+1].start() if i+1 < len(cc_matches) else len(text)
                    segment_text = text[start_pos:end_pos].lower()
                    
                    is_valid = False
                    
                    if logic_mode == 'AND':
                        if all((k in header_text or k in segment_text) for k in keywords):
                            is_valid = True
                    else: 
                        if any((k in header_text or k in segment_text) for k in keywords):
                            is_valid = True
                            
                    if is_valid:
                        if cc_details not in scraped_data:
                            scraped_data.append(cc_details)
                            count += 1
                            keyword_match_count += 1
                            
                            if count >= target_amount:
                                break
                
                if count >= target_amount:
                    break

        if scraped_data:
            with open("scraped_cards.txt", "a", encoding="utf-8") as f:
                for card in scraped_data:
                    f.write(f"{card}\n")
            
            session_filename = f"results_{len(scraped_data)}_cards.txt"
            with open(session_filename, "w", encoding="utf-8") as f:
                for card in scraped_data:
                    f.write(f"{card}\n")

            file_msg = f"✅ **Goal Reached!**" if count >= target_amount else f"⚠️ **Finished (End of History)**"
            
            await status_msg.edit(
                f"{file_msg}\n\n"
                f"📝 Scanned: `{scanned_count}`\n"
                f"🔍 Keywords Matched: `{keyword_match_count}`\n"
                f"💳 Cards Extracted: `{count}` / `{target_amount}`\n"
                f" Sending file..."
            )
            
            await client.send_document(
                message.chat.id,
                session_filename,
                caption=f"💳 Here are the {len(scraped_data)} cards found."
            )
            
            try:
                os.remove(session_filename)
            except Exception as e:
                await status_msg.reply(f"⚠️ Warning: Could not delete file: {e}")

        else:
            await status_msg.edit("❌ No cards found matching criteria.")

    except Exception as e:
        await status_msg.edit(f"⚠️ Critical Error: {str(e)}")


async def main():
    print("🤖 Starting Pyrogram Bot and Userbot...")
    await user_client.start()
    await bot_client.start()
    print("✅ System Online!")
    
    await asyncio.gather(
        pyrogram.idle(),
    )
    
    await user_client.stop()
    await bot_client.stop()

if __name__ == '__main__':
    import pyrogram
    
    loop = asyncio.get_event_loop()

    loop.run_until_complete(main())
