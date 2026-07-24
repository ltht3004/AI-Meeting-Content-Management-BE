import google.generativeai as genai
from fastapi import HTTPException
from app.core.config import settings

async def summarize_transcript(transcript: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured in environment variables."
        )

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-3.5-flash')

        prompt = f"""You are an excellent professional executive assistant. Below is the transcript of a meeting. Please read it carefully, analyze it, and write a highly professional and clear summary.
CRITICAL INSTRUCTION 1: You MUST write the summary in the EXACT SAME LANGUAGE as the original transcript provided below.
CRITICAL INSTRUCTION 2: DO NOT use any Markdown formatting! DO NOT use asterisks (*), hashtags (#), or dashes (---) for headers or horizontal lines. Use PLAIN TEXT ONLY. Use a simple dash (-) for bullet points. Do not make the text bold.
CRITICAL INSTRUCTION 3: If there are NO Decisions or NO Action Items, you MUST COMPLETELY OMIT that section. Do not write "No decisions were made." - just skip the section entirely.
CRITICAL INSTRUCTION 4: The section headers (e.g., "1. Main Content", "2. Decisions", "3. Action Items") MUST be translated into the EXACT SAME LANGUAGE as the transcript. Do NOT use bilingual headers like "Main Content / Nội dung chính". Use ONLY the appropriate language.

The structure of the summary must be EXACTLY like this (using plain text, translated to the transcript's language):

1. [Translated 'Main Content']:
[A brief summary of the key topics and central discussions]

2. [Translated 'Decisions']:
[Clearly list all the decisions that were agreed upon. OMIT THIS ENTIRE SECTION IF NONE]

3. [Translated 'Action Items']:
[Specific tasks to be done, including the assignee and deadline. OMIT THIS ENTIRE SECTION IF NONE]

Meeting Transcript:
{transcript}
"""
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to generate AI summary: {str(e)}"
        )
