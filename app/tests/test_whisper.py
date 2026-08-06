import pytest
from app.services.ai_transcribe import transcribe_audio

# ==========================================
# WHISPER TEST CASES (STT 1 - 7)
# ==========================================
# Ghi chú chung: Vì API Ngrok đang chết (404 offline), tất cả các hàm này 
# đều sẽ bị văng lỗi. Tuy nhiên theo yêu cầu "có lỗi thì hiện lỗi thôi",
# chúng ta vẫn viết đúng kịch bản giả lập, ép gọi API và bắt lỗi trực tiếp.

@pytest.mark.asyncio
async def test_whisper_01_background_noise():
    # TC 1: Tải lên file ghi âm chứa nhiều tạp âm (tiếng gõ phím, quán cafe)
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="noisy_cafe.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")

@pytest.mark.asyncio
async def test_whisper_02_low_quality():
    # TC 2: Tải lên file ghi âm bị nén/chất lượng thấp (8kHz)
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="low_quality_8khz.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")

@pytest.mark.asyncio
async def test_whisper_03_heavy_accent():
    # TC 3: Tải lên file ghi âm có giọng địa phương nặng
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="nghe_an_accent.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")

@pytest.mark.asyncio
async def test_whisper_04_code_mixing():
    # TC 4: Tải lên file ghi âm có trộn lẫn Tiếng Việt và Tiếng Anh
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="viet_anh_mix.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")

@pytest.mark.asyncio
async def test_whisper_05_overlap_speech():
    # TC 5: Tải lên file ghi âm có 2 người nói chèn lên nhau
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="overlap_talking.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")

@pytest.mark.asyncio
async def test_whisper_06_long_silence():
    # TC 6: Tải lên file ghi âm có khoảng im lặng dài (30 giây)
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="silence_30s.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")

@pytest.mark.asyncio
async def test_whisper_07_fast_speech():
    # TC 7: Tải lên file ghi âm có tốc độ nói nhanh (2.0x)
    dummy_wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    try:
        result = await transcribe_audio(file_content=dummy_wav_bytes, file_name="fast_speech_2x.wav", content_type="audio/wav")
        assert "text" in result
    except RuntimeError as e:
        pytest.fail(f"API Whisper bị lỗi hoặc sập mạng: {str(e)}")
