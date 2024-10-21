import os
import base64
from together import Together

# Initialize the Together client using the API key from environment variables
client = Together(api_key='a03116064757c906bff7ca9a40eaef599459518e015dc767c9cdabb23a5a1ec2')

def create_from_data(data, output_dir, number_of_narrations):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_number = 0
    for element in data:

        if element["type"] != "image":
            continue
        if image_number >= number_of_narrations:
            break
        image_number += 1
        image_name = f"image_{image_number}.webp"
        prompt = element["description"] + ". horizontal image, fully filling the canvas."
        generate(prompt, os.path.join(output_dir, image_name))

def generate(prompt, output_file, width=1792, height=1024, steps=4):
    response = client.images.generate(
        model="black-forest-labs/FLUX.1-schnell",
        prompt=prompt,
        width=width,
        height=height,
        steps=steps,
        n=1,
        response_format="b64_json"
    )

    # Extract the base64 image data from the response
    image_b64 = response.data[0].b64_json

    # Decode and save the image to the specified output file
    with open(output_file, "wb") as f:
        f.write(base64.b64decode(image_b64))


