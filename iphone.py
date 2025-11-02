from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from openai import OpenAI
from pydub import AudioSegment
from datetime import datetime
import os
import uvicorn

app = FastAPI()
client = OpenAI()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/upload_audio")
async def upload_audio(request: Request, file: UploadFile = File(None)):
    """
    Receives audio from iPhone Shortcut, transcribes it with Whisper,
    asks GPT for a response, converts GPT response to TTS, and returns MP3.
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1️⃣ Accept audio (both raw File or multipart Form)
    if file is not None:
        filename = file.filename or f"recording_{timestamp}.m4a"
        data = await file.read()
        print(f"✅ Received multipart file ({len(data)} bytes)")
    else:
        data = await request.body()
        filename = f"recording_{timestamp}.m4a"
        print(f"✅ Received raw binary body ({len(data)} bytes)")

    original_path = os.path.join(UPLOAD_DIR, filename)
    with open(original_path, "wb") as f:
        f.write(data)

    # 2️⃣ Convert to MP3 for consistency
    try:
        audio = AudioSegment.from_file(original_path)
        mp3_path = os.path.splitext(original_path)[0] + ".mp3"
        audio.export(mp3_path, format="mp3")
        print(f"🎧 Converted to MP3: {mp3_path}")
    except Exception as e:
        print(f"⚠️ Conversion failed: {e}")
        return JSONResponse({"error": str(e)})

    # 3️⃣ Transcribe the MP3 (Speech → Text)
    with open(mp3_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f
        )
    question = transcript.text.strip()
    print(f"🗣️ Transcribed: {question}")

    # 4️⃣ Ask GPT for a response (Text → Text)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Jarvis, a concise, friendly AI assistant."},
            {"role": "user", "content": question}
        ]
    )
    answer = completion.choices[0].message.content.strip()
    print(f"🤖 Jarvis: {answer}")

    # 5️⃣ Generate TTS (Text → Speech)
    tts = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=answer
    )

    response_path = os.path.join(UPLOAD_DIR, f"response_{timestamp}.mp3")
    tts.stream_to_file(response_path)
    print(f"🔊 TTS saved: {response_path}")

    # 6️⃣ Return the TTS MP3 so the iPhone can play it directly
    return FileResponse(
        response_path,
        media_type="audio/mpeg",
        filename=os.path.basename(response_path)
    )


if __name__ == "__main__":
    uvicorn.run("iphone:app", host="0.0.0.0", port=8000)
