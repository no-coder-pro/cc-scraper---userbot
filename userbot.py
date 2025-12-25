import asyncio
import os
import re
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.errors import UserAlreadyParticipantError

# API Credentials
API_ID = 27815887
API_HASH = 'dbb31988b20945abd1ee1311f543b19f'
BOT_TOKEN = '8374477649:AAGbWTlSlf_zthKpfeQXqIyyYu3q9dyArkg'

user_client = TelegramClient('anon', API_ID, API_HASH)
bot_client = TelegramClient('bot', API_ID, API_HASH)

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

@bot_client.on(events.NewMessage(pattern=r'/start'))
async def start_command(event):
    await event.reply(
        "👋 **Hello! I am your Scraper Bot.**\n\n"
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

@bot_client.on(events.NewMessage(pattern=r'/scr'))
async def scrape_command(event):
    target, keywords, logic_mode, target_amount = parse_arguments(event.text)
    
    if not target or not target_amount:
        await event.reply("❌ Invalid Format.\nUse: `/scr <target> [optional/keywords] <amount>`")
        return

    status_msg = await event.reply(
        f"⏳ **Processing...**\n"
        f"Target: `{target}`\n"
        f"Keywords: `{', '.join(keywords)}` ({logic_mode} logic)\n"
        f"Goal: `{target_amount}` cards"
    )

    try:
        entity = None
        if "t.me/+" in target or "joinchat" in target:
            invite_hash = target.split('+')[-1] if '+' in target else target.split('joinchat/')[-1]
            invite_hash = invite_hash.replace('/', '')
            try:
                updates = await user_client(ImportChatInviteRequest(invite_hash))
                entity = updates.chats[0]
                await status_msg.edit(f"✅ Userbot joined **{entity.title}**!")
            except UserAlreadyParticipantError:
                try:
                    invite_info = await user_client(CheckChatInviteRequest(invite_hash))
                    if hasattr(invite_info, 'chat'):
                        entity = invite_info.chat
                        await status_msg.edit(f"⚠️ Userbot already in **{getattr(entity, 'title', 'Group')}**.")
                    else:
                        await status_msg.edit("❌ Already in group but couldn't resolve entity.")
                        return
                except Exception as e:
                    await status_msg.edit(f"❌ Error resolving invite: {e}")
                    return
            except Exception as e:
                await status_msg.edit(f"❌ Join Error: {e}")
                return
        else:
            try:
                entity = await user_client.get_entity(target)
            except Exception as e:
                await status_msg.edit(f"❌ Could not find entity `{target}`: {e}")
                return

        await status_msg.edit(f"🔍 **Scraping {getattr(entity, 'title', target)}...**\nLooking for: {', '.join(keywords)}")

        count = 0
        scanned_count = 0
        keyword_match_count = 0
        scraped_data = []

        async for message in user_client.iter_messages(entity, limit=None):
            scanned_count += 1
            if scanned_count % 500 == 0:
                await status_msg.edit(
                    f"🔄 **Scanning...**\n"
                    f"Scanned: `{scanned_count}` messages\n"
                    f"Found: `{count}/{target_amount}` cards"
                )

            if message.text:
                text = message.text
                text_lower = text.lower()
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
                            keyword_match_count += 1 # Rough stat
                            
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
                f"� Sending file..."
            )
            
            await event.client.send_file(
                event.chat_id,
                session_filename,
                caption=f"💳 Here are the {len(scraped_data)} cards found."
            )
            
            try:
                os.remove(session_filename)
            except Exception as e:
                await status_msg.respond(f"⚠️ Warning: Could not delete file: {e}")

        else:
            await status_msg.edit("❌ No cards found matching criteria.")

    except Exception as e:
        await status_msg.edit(f"⚠️ Critical Error: {str(e)}")


async def main():
    print("🤖 Starting Bot and Userbot...")
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ System Online!")
    
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())