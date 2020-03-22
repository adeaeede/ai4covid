import base64
from io import BytesIO
from json import dumps

import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image
from flask import Flask, Response, request
from flask_cors import CORS, cross_origin

from api.model import Covid19Net

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
model = Covid19Net.load_model('res/model.pth.tar', device=torch.device('cpu'))

_transform = transforms.Compose([
    transforms.Resize(224),
    transforms.CenterCrop(224)
])


def encode_image(_bytes):
    """
    Converts the image into a numpy array for further processing by the model.
    :param _bytes:
    :return: 3D ndarray containing the image
    """
    ndarray = np.fromstring(_bytes, np.uint8)
    ndarray = cv2.imdecode(ndarray, cv2.IMREAD_COLOR)
    image = Image.fromarray(ndarray)
    return image

def base64_to_image(base64_string):
    """
    :param base64_string: base64 string
    :return: PIL Image
    """
    return Image.open(BytesIO(base64.b64decode(base64_string)))


def array_to_base64(array):
    """
    :param array: Numpy array
    :return: base64 string
    """
    return base64.b64encode(array)


def generate_heatmap_image(image):
    """
    :param image: PIL Image
    :return: Numpy array (height, width, channels)
    """
    # resize and center crop the input image
    image = _transform(image)
    # generate heatmap using the network
    heatmap = Covid19Net.generate_heatmap(model, image).numpy()
    # normalize heatmap
    heatmap = heatmap / np.max(heatmap)
    # resize to match input image dimensions
    heatmap = cv2.resize(heatmap, (224, 224))
    # apply color map to the heatmap
    heatmap = cv2.applyColorMap(np.uint8(255 * heatmap), cv2.COLORMAP_JET)
    # apply heatmap to the input image
    image_array = np.array(image)
    heatmap_image = cv2.addWeighted(image_array, 1, heatmap, 0.35, 0)
    heatmap_image = cv2.cvtColor(heatmap_image, cv2.COLOR_BGR2RGB)
    return heatmap_image


@app.route('/api/v1/classify/', methods=['POST'])
@cross_origin()
def classify():
    """
    Classifies objects detected in the provided image.
    :return: Class score.
    """
    bytes = request.files['file'].stream.read()
    image = encode_image(bytes)
    prediction = Covid19Net.predict(model, image)
    heatmap_image = generate_heatmap_image(image)
    heatmap_image_base64 = array_to_base64(heatmap_image).decode('utf-8')
    print(heatmap_image_base64)
    response_json = dumps({'prediction': prediction,
                           'heatmap': heatmap_image_base64})
    return Response(response_json, status=200, mimetype='application/json')


if __name__ == '__main__':
    # Set debug=False and threaded=False otherwise the model throws exceptions
    # Set debug=True for developing the API without using the model
    app.run(debug=True, threaded=False, host='localhost', port='8000')
