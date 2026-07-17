#!/usr/bin/env python3
import asyncio, asyncpg, json, os
ROWS = json.loads('[{"key": "ai_routing_assignments", "value": "{\\"channel_name\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"channel_description\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"channel_keywords\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"channel_tags\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"lyric\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"title\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"album\\":{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},\\"channel_logo\\":{\\"provider\\":\\"fal\\",\\"sub_model\\":\\"flux-pro\\",\\"is_active\\":true},\\"channel_cover\\":{\\"provider\\":\\"fal\\",\\"sub_model\\":\\"flux-pro\\",\\"is_active\\":true},\\"background_image\\":{\\"provider\\":\\"slai\\",\\"sub_model\\":\\"slai/gpt-image-2\\",\\"is_active\\":true},\\"thumbnail_image\\":{\\"provider\\":\\"slai\\",\\"sub_model\\":\\"slai/gpt-image-2\\",\\"is_active\\":true},\\"music\\":{\\"provider\\":\\"suno\\",\\"sub_model\\":null,\\"is_active\\":true}}", "value_type": "json"}, {"key": "ai_routing_image_fallback_chain", "value": "[{\\"provider\\":\\"slai\\",\\"sub_model\\":\\"slai/gpt-image-2\\",\\"is_active\\":true},{\\"provider\\":\\"fal\\",\\"sub_model\\":\\"flux-pro\\",\\"is_active\\":true},{\\"provider\\":\\"openai\\",\\"sub_model\\":\\"gpt-image-1\\",\\"is_active\\":true}]", "value_type": "json"}, {"key": "ai_routing_text_fallback_chain", "value": "[{\\"provider\\":\\"deepseek\\",\\"sub_model\\":\\"deepseek-chat\\",\\"is_active\\":true},{\\"provider\\":\\"slai\\",\\"sub_model\\":\\"xiaomi/mimo-v2.5-pro\\",\\"is_active\\":true},{\\"provider\\":\\"openai\\",\\"sub_model\\":\\"gpt-4o-mini\\",\\"is_active\\":true}]", "value_type": "json"}]')
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    for row in ROWS:
        await conn.execute(
            '''
            INSERT INTO system_settings (key, value, value_type, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (key) DO UPDATE SET
              value = EXCLUDED.value,
              value_type = EXCLUDED.value_type,
              updated_at = NOW()
            ''',
            row["key"], row["value"], row["value_type"],
        )
        print("upsert", row["key"])
    await conn.close()
asyncio.run(main())
