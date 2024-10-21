from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import time
import json
import narration
import torch
from together import Together
import subprocess
import images
import video2
import signal
import shutil
import sys
# from pyngrok import ngrok


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/videos'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi'}
folder_to_cleanup = os.path.join('static', 'videos')

def cleanup_folder(folder_path):
    # Delete all files and subdirectories in the specified folder
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # Remove the file or link
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Remove the directory and its contents
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def signal_handler(sig, frame):
    print("\nShutting down the app and cleaning up files...")
    cleanup_folder(folder_to_cleanup)
    print("Cleanup complete. Exiting.")
    # Exit the application
    os._exit(0)

# Register the signal handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Function to convert AVI to MP4
def convert_to_mp4(basedir, output_file):
    input_path = os.path.join(basedir, output_file)
    output_file_mp4 = os.path.splitext(output_file)[0] + '.mp4'
    output_path = os.path.join(basedir, output_file_mp4)

    # Use ffmpeg to convert the video to mp4
    command = [
        'ffmpeg', '-i', input_path,
        '-vcodec', 'libx264',
        '-acodec', 'aac',
        '-strict', 'experimental',
        output_path
    ]
    try:
        subprocess.run(command, check=True)
        print(f"DONE! Here's your video: {output_path}")
        return output_file_mp4  # Return the name of the mp4 file
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        return None  # Return None if there was an error
def load_model():
# Use the specified model ID and fetch the Together client
    client = Together(api_key='a03116064757c906bff7ca9a40eaef599459518e015dc767c9cdabb23a5a1ec2')

    def generate_response(prompt):
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,  # Limit the response length
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>", "<|eom_id|>"],
            stream=False  # Turn off streaming to get the full response directly
        )
        return response.choices[0].message.content

    return generate_response

def generate_industrial_hemp_response(source_material):
    generator = load_model()
    # Define the prompt
    prompt = f"""
    You are a helpful assistant. Please answer the following question. Questions will be centered around Industrial Hemp. 
    No matter what question you are not supposed to generate anything with impact on health from hemp. Do not mention 'Cannabis', 'Marijuana' ,'Weed'. Only talk about Industrial Hemp. 
    The response should be 12 complete sentences long only with each sentence no more than 48 tokens, to fit in a 1 min narration. Don't answer in bullet points only paragraphs. Answers should be in a visual langauge.

    Answer this question: {source_material}
    """

    # Generate the response
    answer = generator(prompt)
    # Extract the generated text
    return answer

def generate_narration(answer):
    # Define the prompt similar to your OpenAI prompt
    generator = load_model()
    prompt = f"""
    You are a YouTube short narration generator. You generate 1 minute of narration. The shorts you create have a background that fades from image to image as the narration is going on.

    You will need to generate descriptions of images for each of the sentences in the short. They will be passed to an AI image generator. DO NOT IN ANY CIRCUMSTANCES use names of celebrities or people in the image descriptions. It is illegal to generate images of celebrities. Only describe persons without their names. Do not reference any real person or group in the image descriptions. Don't mention the female figure or other sexual content in the images because they are not allowed.Do not mention 'Cannabis', 'Marijuana' ,'Weed'. Only talk about Industrial Hemp.

    You are however allowed to use any content, including real names in the narration. Only image descriptions are restricted.

    Note that the narration will be fed into a text-to-speech engine, so don't use special characters.

    Respond with a pair of an image description in square brackets and a narration below it. Both of them should be on their own lines, as follows:

    ###

    [Description of a background image]

    Narrator: "One sentence of narration"

    [Description of a background image]

    Narrator: "One sentence of narration"

    [Description of a background image]

    Narrator: "One sentence of narration"

    ###

    The narration sentence should be same as each sentence given to you. Each sentence will come with the image description, there are only 12 sentences given to you. Dont talk about filenames.

    You should add a description of a fitting background image in between all of the narrations. It will later be used to generate an image with AI.

    Based on the following answer: {answer}, create a YouTube short narration.

    """

    
    # Extract the generated text
    narrations = generator(prompt)
    return narrations

@app.route('/', methods=['GET', 'POST'])

def index():
    video_path = None
    if request.method == 'POST':
        source_material = request.form['question']
        caption_settings = {}
        short_id = "videos"
        output_file = "short.avi"
        basedir = os.path.join("static", short_id)

        if not os.path.exists(basedir):
            os.makedirs(basedir)
        
        print("Generating script...")

        response_output = generate_industrial_hemp_response(source_material)
        answer = response_output
        narration_response = generate_narration(answer)

        with open(os.path.join(basedir, "response.txt"), "w") as f:
            f.write(narration_response)

        data, narrations = narration.parse(narration_response)

        with open(os.path.join(basedir, "data.json"), "w") as f:
            json.dump(data, f, ensure_ascii=False)

        print("Generating narration...")
        number_of_narrations = narration.create(data, os.path.join(basedir, "narrations"))

        print("Generating images...")
        images.create_from_data(data, os.path.join(basedir, "images"), number_of_narrations)

        print("Generating video...")
        video2.create(narrations, basedir, output_file, caption_settings)

        video_path = os.path.join('videos', output_file)
        print(f"DONE! Here's your video: {video_path}")

        mp4_video = convert_to_mp4(basedir, output_file)
        return json.dumps({'video_path': url_for('serve_video', filename=mp4_video)})

    return render_template('index.html', video_path=video_path)

@app.route('/static/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory('static/videos', filename)

if __name__ == '__main__':
    app.run(debug=True)