import textwrap
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import openai
import os
from pydub import AudioSegment
from langchain.chat_models import ChatOpenAI
from langchain.prompts.chat import ChatPromptTemplate
import argparse
import sounddevice as sd
import asyncio
import datetime

def split_audio(input_filename, output_directory, chunk_length_ms):
    audio = AudioSegment.from_file(input_filename)
    
    total_length_ms = len(audio)
    
    for i in range(0, total_length_ms, chunk_length_ms):
        chunk = audio[i:i + chunk_length_ms]
        chunk = chunk.set_frame_rate(16000) # max frame rate that whisper supports
        chunk_name = f"{output_directory}/chunk{i//1000}_{(i + chunk_length_ms)//1000}.mp3"
        chunk.export(chunk_name, format="mp3")

async def transcribe_audio(file_path):
    loop = asyncio.get_event_loop()
    with open(file_path, 'rb') as f:
        transcript = await loop.run_in_executor(None, openai.Audio.transcribe, "whisper-1", f)
    return transcript.text

async def transcribe_directory(directory_path):
    audio_files = [os.path.join(directory_path, filename) for filename in sorted(os.listdir(directory_path)) if filename.endswith(".mp3")]
    tasks = [asyncio.create_task(transcribe_audio(audio_file)) for audio_file in audio_files]
    transcripts = await asyncio.gather(*tasks)
    # cleanup audio_chunks directory
    for filename in audio_files:
        os.remove(filename)
    return " ".join(transcripts)

async def async_run(chunk, chain):
    resp = await chain.arun(text=chunk)
    return resp

async def async_invoke(chunk, note_type, chain):
    resp = await chain.ainvoke({"text": chunk, "note_type": note_type})
    return resp.content

async def generate_notes(model, note_type, transcription):
    if model == 'davinci':
        llm = OpenAI(model_name="text-davinci-003")
        prompt = PromptTemplate(
            input_variables=["transcription"],
            template="Take notes on the following text {text}. \n Respond with just the notes",
        )
        chain = LLMChain(llm=llm, prompt=prompt)
        chunks = textwrap.wrap(transcription, 2000) 
        notes = list()
        tasks = [asyncio.create_task(async_run(chunk, chain)) for chunk in chunks]
        notes = await asyncio.gather(*tasks)

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"notes_{timestamp}.txt"
        with open(filename, 'w') as f:
            f.write("\n".join(notes))
        print(f"Notes saved to {filename}")
    else:        
        if model == 'gpt-3.5':
            llm = ChatOpenAI(model_name='gpt-3.5-turbo-1106')
        elif model == 'gpt-4':
            llm = ChatOpenAI(model_name='gpt-4-1106-preview')

        if note_type == "md":
            prompt_note_type = "markdown"
        else:
            prompt_note_type = "plain text"

        text_prompt = """You will be provided with a transcription from a lecture/meeting/speech/video\
        Your task is to take highly detailed notes on the information present in the transcription in order for someone to study from it \
        do not loose any of the important information from the transcription. Use headings to divide up the topics if necessary. Also add some review questions on the most important pieces of content \
        at the end. Use the ENTIRE context window of the transcription. Make sure your response is in {note_type} format. do not include "```md or ```" The transcription is: {text} 
        """  

        prompt = ChatPromptTemplate.from_template(text_prompt)
        chain = prompt | llm
        chunks = textwrap.wrap(transcription, 6000) 
        notes = list()
        tasks = [asyncio.create_task(async_invoke(chunk, prompt_note_type, chain)) for chunk in chunks]
        notes = await asyncio.gather(*tasks)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"notes_{timestamp}.{note_type}"
        with open(filename, 'w') as f:
            f.write("\n".join(notes))
        print(f"Notes saved to {filename}")
    return notes
    
def find_microphone():
    # list all available audio input devices
    devices = sd.query_devices()
    mic_keyword = "Microphone"
    exclude_keyword = "iPhone"

    # find the first appropriate microphone device
    for device in devices:
        if device['max_input_channels'] > 0:  # device must be an input device
            if mic_keyword in device['name'] and exclude_keyword not in device['name']:
                mic_index = device['index']
                print(f"Selected microphone: {device['name']} with index {mic_index}")
                return mic_index

    print("No suitable microphone found.")
    return None

async def main():
    pass
    # DEPRECATED Main method now that GUI exists
    # parser = argparse.ArgumentParser(description='A Python script that generates notes with AI')
    # parser.add_argument('--model', choices=['davinci', 'gpt-3.5', 'gpt-4'], type=str, help='choose model', default='davinci')
    # args = parser.parse_args()
    # output_filename = "speech.wav"
    # if os.path.exists(output_filename):
    #     os.remove(output_filename)

    # device_index = find_microphone()
    # try:
    #     record_audio.record_audio(filename=output_filename, device=device_index, samplerate=16000, channels=1, subtype='PCM_24')
    # except Exception as e:
    #     print(f"An error occurred: {e}")
    # audio_file= open(output_filename, "rb")
    # output_directory = "audio_chunks"
    # chunk_length_ms = 10 * 60 * 1000  # 10 minutes in milliseconds
    
    # # create the output directory if it doesn't exist
    # if not os.path.exists(output_directory):
    #     os.makedirs(output_directory)
    # split_audio(audio_file, output_directory, chunk_length_ms)

    # transcription = await transcribe_directory(output_directory)
    # print(transcription)
    # # delete audio file once we are done with it
    # if os.path.exists(output_filename):
    #     os.remove(output_filename)

    # generate_notes(args.model, transcription)        


if __name__ == "__main__":
    asyncio.run(main())
