import logging
from typing import List

import numpy as np
import tensorflow as tf
from skimage import transform

from src import pyutils
from src.face_recognition.dto.bounding_box import BoundingBox
from src.face_recognition.dto.cropped_face import CroppedFace
from src.face_recognition.embedding_classifier.libraries import facenet
from src.face_recognition.face_cropper.constants import FACE_MIN_SIZE, DEFAULT_1ST_THRESHOLD, DEFAULT_2DN_THRESHOLD, DEFAULT_3RD_THRESHOLD, SCALE_FACTOR, FaceLimitConstant, \
    MARGIN, IMAGE_SIZE, FaceLimit
from src.face_recognition.face_cropper.exceptions import IncorrectImageDimensionsError, NoFaceFoundError
from src.face_recognition.face_cropper.libraries.align import detect_face

pnet, rnet, onet = None, None, None


@pyutils.run_once
def _init_once():
    with tf.Graph().as_default():
        global pnet, rnet, onet
        sess = tf.Session()
        pnet, rnet, onet = detect_face.create_mtcnn(sess, None)
    return pnet, rnet, onet


def crop_face(img, detection_3rd_threshold = DEFAULT_3RD_THRESHOLD) -> CroppedFace:
    cropped_faces = crop_faces(img, detection_3rd_threshold, face_lim=1)
    return cropped_faces[0]



def _get_bounding_boxes(img, face_lim, detection_3rd_threshold):

    detect_face_result = detect_face.detect_face(img, FACE_MIN_SIZE, pnet, rnet, onet, [DEFAULT_1ST_THRESHOLD, DEFAULT_2DN_THRESHOLD, detection_3rd_threshold], SCALE_FACTOR)
    bounding_boxes = list(detect_face_result[0])
    if len(bounding_boxes) < 1:
        raise NoFaceFoundError("No face is found in the given image")
    if face_lim:
        return bounding_boxes[:face_lim]
    return bounding_boxes



def _bounding_box_2_cropped_face(bounding_box, img, img_size) -> CroppedFace:
    logging.debug(f"the box around this face has dimensions of {bounding_box[0:4]}")
    is_face_prob = bounding_box[4]
    bounding_box = np.squeeze(bounding_box)
    xmin = int(np.maximum(bounding_box[0] - MARGIN / 2, 0))
    ymin = int(np.maximum(bounding_box[1] - MARGIN / 2, 0))
    xmax = int(np.minimum(bounding_box[2] + MARGIN / 2, img_size[1]))
    ymax = int(np.minimum(bounding_box[3] + MARGIN / 2, img_size[0]))
    cropped_img = img[ymin:ymax, xmin:xmax, :]
    resized_img = transform.resize(cropped_img, (IMAGE_SIZE, IMAGE_SIZE))
    return CroppedFace(box=BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax), img=resized_img, is_face_prob=is_face_prob)


def _preprocess_img(img):
    if img.ndim < 2:
        raise IncorrectImageDimensionsError("Unable to align image, it has only one dimension")
    img = facenet.to_rgb(img) if img.ndim == 2 else img
    img = img[:, :, 0:3]
    img_size = np.asarray(img.shape)[0:2]
    return img, img_size


@pyutils.run_first(_init_once)
def crop_faces(img, detection_3rd_threshold = DEFAULT_3RD_THRESHOLD, face_lim: FaceLimit = FaceLimitConstant.NO_LIMIT) -> List[CroppedFace]:
    img, img_size = _preprocess_img(img)
    bounding_boxes = _get_bounding_boxes(img, face_lim, detection_3rd_threshold)
    cropped_faces = [_bounding_box_2_cropped_face(bounding_box, img, img_size) for bounding_box in bounding_boxes]
    return cropped_faces

if __name__ == "__main__" :
    import os
    from pathlib import Path

    pnet, rnet, onet = None, None, None

    @pyutils.run_once
    def _init_once():
        with tf.Graph().as_default():
            global pnet, rnet, onet
            sess = tf.Session()
            pnet, rnet, onet = detect_face.create_mtcnn(sess, None)


    CURRENT_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
    def draw_bounding_box(nparray, bounding_box):
        color = np.array([0, 255, 0], dtype=np.uint8)
        nparray[int(bounding_box[1]), int(bounding_box[0]):int(bounding_box[2])] = color
        nparray[int(bounding_box[1]):int(bounding_box[3]), int(bounding_box[0])] = color
        nparray[int(bounding_box[3]), int(bounding_box[0]):int(bounding_box[2])] = color
        nparray[int(bounding_box[1]):int(bounding_box[3]),  int(bounding_box[2])] = color


    def show_image(nparray):
        from PIL import Image
        Image.fromarray(nparray, 'RGB').show()


    def crop_faces_TEST(img, detection_3rd_threshold = DEFAULT_3RD_THRESHOLD, face_lim: FaceLimit = FaceLimitConstant.NO_LIMIT) -> List[CroppedFace]:
        img, img_size = _preprocess_img(img)
        bounding_boxes = _get_bounding_boxes(img, face_lim, detection_3rd_threshold)
        arr = img.astype(np.uint8)
        for bounding_box in bounding_boxes:
            draw_bounding_box(arr, bounding_box[0:4])
        show_image(arr)

    def number_of_boxes_test(img, detection_3rd_threshold, face_lim: FaceLimit = FaceLimitConstant.NO_LIMIT):
        img, img_size = _preprocess_img(img)
        bounding_boxes = _get_bounding_boxes(img, face_lim, detection_3rd_threshold)
        return len(bounding_boxes)

    import imageio

    _init_once()
    im = imageio.imread(CURRENT_DIR / 'test' / 'files' / 'eight-faces.png')
    crop_faces_TEST(im)

    im = imageio.imread(CURRENT_DIR / 'test' / 'files' / 'eight-faces.jpg')
    crop_faces_TEST(im)

    def test_for_boxes_for_diff_thresholds():
        _init_once()
        CURRENT_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
        IMG_DIR = CURRENT_DIR / 'tool_find_threshold' / 'files'

        DATASET = [
            IMG_DIR / 'four-faces.png',
            IMG_DIR / 'four-faces.jpg',
            IMG_DIR / 'four-plus-one-faces.png',
            IMG_DIR / 'four-plus-one-faces.jpg',
            IMG_DIR / 'five-people.png',
            IMG_DIR / 'five-people.jpg',
            IMG_DIR / 'six-faces.png',
            IMG_DIR / 'six-faces.jpg',
            IMG_DIR / 'eight-faces.png',
            IMG_DIR / 'eight-faces.jpg',
            IMG_DIR / 'five-faces.png',
            IMG_DIR / 'two-faces.png',
            IMG_DIR / 'two-faces.jpg',
            IMG_DIR / 'three-people.png',
            IMG_DIR / 'three-people.jpg',
            IMG_DIR / 'four-people.png',
            IMG_DIR / 'four-people.jpg'
        ]

        for picture in DATASET:
            im = imageio.imread(picture)
            len_our_threshold = number_of_boxes_test(im, detection_3rd_threshold=None)
            len_new_threshold = number_of_boxes_test(im, 0.1)
            if len_new_threshold == len_our_threshold:
                print(picture, ":", "the number of boxes has not changed")
            else:
                print(picture, ":", len_new_threshold, len_our_threshold)

    #test_for_boxes_for_diff_thresholds()