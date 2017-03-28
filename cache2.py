# Adapted from source code provided by Udacity

from keras.applications.resnet50 import ResNet50, preprocess_input
from keras.applications.inception_v3 import InceptionV3
from keras.applications.vgg16 import VGG16
from keras.layers import Input, AveragePooling2D
from sklearn.model_selection import train_test_split
from keras.models import Model
from keras.datasets import cifar10
from math import ceil
import pickle
import tensorflow as tf
import keras.backend as K
import numpy as np
import csv
import cv2
import matplotlib.pyplot as plt

flags = tf.app.flags
FLAGS = flags.FLAGS

flags.DEFINE_string('dataset', '.', "Path to the dataset")
flags.DEFINE_string('network', 'resnet', "The model to bottleneck, one of 'vgg', 'inception', or 'resnet'")
flags.DEFINE_integer('batch_size', 24, 'The batch size for the generator')

batch_size = FLAGS.batch_size

# Set the input size expected by the model. TODO how to do to adjust to my input size?
h, w, ch = 224, 224, 3
if FLAGS.network == 'inception':
    h, w, ch = 299, 299, 3
    from keras.applications.inception_v3 import preprocess_input

# Used to resize the input images as necessary. I can use it, but is it OK to change aspect ratio?
img_placeholder = tf.placeholder("uint8", (None, 160 - 70 - 25, 320, 3))
resize_op = tf.image.resize_images(img_placeholder, (h, w), method=0)


def pre_process(image):
    # Convert to desired color space
    image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Crop 70, 25
    image_h = image.shape[0]
    image = image[70:image_h - 25, :]
    # Resize to meet the required input size for the NN
    image = cv2.resize(image, (h, w))
    # Ensure range of pixels is in [-1, 1]
    image = (image / 255 - .5) * 2
    return image


def create_model():
    input_tensor = Input(shape=(h, w, ch))
    if FLAGS.network == 'vgg':
        model = VGG16(input_tensor=input_tensor, include_top=False)
        x = model.output
        x = AveragePooling2D((7, 7))(x)
        model = Model(model.input, x)
    elif FLAGS.network == 'inception':
        model = InceptionV3(input_tensor=input_tensor, include_top=False)
        x = model.output
        x = AveragePooling2D((8, 8), strides=(8, 8))(x)
        model = Model(model.input, x)
    else:
        model = ResNet50(input_tensor=input_tensor, include_top=False)
    return model


def load_telemetry(fname):
    # Load telemetry from the dataset
    telemetry = []
    with open(fname) as csv_file:
        reader = csv.reader(csv_file)
        header = True
        for line in reader:
            if header:
                header = False
                continue
            telemetry.append(line)

    telemetry = np.array(telemetry)
    return telemetry


def load_dataset(telemetry, base_dir, offset, batch_size):
    images, angles = [], []
    for i in range(offset, offset+batch_size):
        if i >= len(telemetry):
            break
        item = telemetry[i]
        name = base_dir + '/IMG/' + item[0].split('/')[-1]
        center_image = cv2.imread(name)
        assert center_image is not None
        center_image = pre_process(center_image)
        center_angle = float(item[3])
        images.append(center_image)
        angles.append(center_angle)

    X = np.array(images)
    y = np.array(angles)
    return X, y


def main():
    # Load csv file with telemetry
    # Base directory for the dataset
    dataset_dir = FLAGS.dataset
    csv_fname = dataset_dir + '/driving_log.csv'
    telemetry = load_telemetry(csv_fname)
    print('Read', len(telemetry), 'lines from input csv file', csv_fname)

    sess = tf.Session()
    sess.as_default()
    K.set_session(sess)
    K.set_learning_phase(1)
    model = create_model()
    n_samples = len(telemetry)
    batch_count = 0
    print("Resizing to", (w, h, ch))
    n_batches = ceil(n_samples/batch_size)
    X_cache = []
    for offset in range(0, n_samples, batch_size):
        print('Processing batch {}/{}'.format(batch_count+1, n_batches))
        # Load the dataset
        X, y = load_dataset(telemetry, dataset_dir, offset, batch_size)
        assert len(X) == len(y) <=batch_size
        bottleneck_features_train = model.predict(X, batch_size=batch_size, verbose=1)
        X_cache.extend(bottleneck_features_train)
        batch_count += 1
    X_cache = np.array(X_cache)
    data = {'features': X_cache, 'labels': telemetry[:, 3]}
    train_output_file = "{}_{}_{}.p".format(FLAGS.network, 'driving', 'bottleneck_features_train')
    pickle.dump(data, open(train_output_file, 'wb'))


if __name__ == '__main__':
    main()