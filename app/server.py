import librosa
from PIL import Image
from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from fastai.vision import *
import torch
from pathlib import Path
from io import BytesIO
import sys
import uvicorn
import aiohttp
import asyncio
import pylab
from PIL import Image
import matplotlib
matplotlib.use('agg')

from matplotlib import pyplot as plt
from matplotlib import cm
from tqdm import tqdm
import pylab

import librosa
from librosa import display
import numpy as np

templates = Jinja2Templates(directory='app/templates')

async def get_bytes(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()

app = Starlette(debug=True)

app.mount('/static', StaticFiles(directory='app/static'))
app.mount('/gifs', StaticFiles(directory='gifs'), name='gifs')


spectrograms_path = Path('spectrographs')

data = ImageDataBunch.from_folder(spectrograms_path, train=".", valid_pct=0.2, ds_tfms=get_transforms(), size=360, num_workers=4).normalize(imagenet_stats) #changed size from 224 to 360

learn = load_learner('app/models')

@app.route("/upload", methods=["POST"])
async def upload(request):
    data = await request.form()
    bytes = await (data["file"].read())
    wav = BytesIO(bytes) #not my favorite way to do this but it works ;)
    with open('sound.wav', 'wb') as f:
        f.write(wav.getvalue())
    wav.close()
    return predict_sound_from_wav()

@app.route("/classify-url", methods=["GET"])
async def classify_url(request):
    bytes = await get_bytes(request.query_params["url"])
    return predict_image_from_bytes(bytes)

def predict_sound_from_wav():
    #convert sound to image
    create_spectrograph("sound.wav", "image.jpg") 

    img_bytes = BytesIO()
    #load image from disk
    with open('image.jpg', 'rb') as f:
         img_bytes = BytesIO(f.read())
    #img_bytes.close()

    #img = Image.open('image.jpg')
    img = open_image(img_bytes)
    _,_,losses = learn.predict(img)
    return JSONResponse({
        "predictions": sorted(
            zip(data.classes, map(float, losses)),
            key=lambda p: p[1],
            reverse=True
        )
    })

@app.route('/')
async def homepage(request):
    return templates.TemplateResponse('index.html', {'request': request})

def create_spectrograph(source_filepath, destination_filepath):    
    y, sr = librosa.load(source_filepath, sr = 22050) # Use the default sampling rate of 22,050 Hz

    # Pre-emphasis filter
    pre_emphasis = 0.97
    y = np.append(y[0], y[1:] - pre_emphasis * y[:-1])

    # Compute spectrogram
    M = librosa.feature.melspectrogram(y, 
                                       sr, 
                                       fmax = sr/2, # Maximum frequency to be used on the on the MEL scale        
                                       n_fft=2048, 
                                       hop_length=512, 
                                       n_mels = 96, # As per the Google Large-scale audio CNN paper
                                       power = 2) # Power = 2 refers to squared amplitude
    # Power in DB
    log_power = librosa.power_to_db(M, ref=np.max)# Covert to dB (log) scale
    
    # Plotting the spectrogram and save as JPG without axes (just the image)
    #pylab.figure(figsize=(5,5)) #was 14, 5
    pylab.axis('off') 
    pylab.axes([0., 0., 1., 1.], frameon=False, xticks=[], yticks=[]) # Remove the white edge
    librosa.display.specshow(log_power, cmap=cm.jet)
    print(destination_filepath)
    pylab.savefig(destination_filepath, bbox_inches=None, pad_inches=0)
    pylab.close()

@app.route("/form")
def redirect_to_homepage(request):
    return RedirectResponse("/")

if __name__ == "__main__":
    if "serve" in sys.argv:
        uvicorn.run(app, host="0.0.0.0", port=8008)
