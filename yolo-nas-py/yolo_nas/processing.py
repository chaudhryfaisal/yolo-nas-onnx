import numpy as np
import cv2


class Preprocessing:
    def __init__(self, steps, out_shape):
        self.steps = steps
        self.out_shape = out_shape

    @staticmethod
    def __rescale_img(img, out_shape):
        return cv2.resize(img, dsize=out_shape, interpolation=cv2.INTER_LINEAR).astype(np.uint8)

    def _standarize(self, img, max_value):
        return (img / max_value).astype(np.float32), None

    def _det_rescale(self, img):
        scale_factor_h, scale_factor_w = (
            self.out_shape[0] / img.shape[0],
            self.out_shape[1] / img.shape[1],
        )
        return self.__rescale_img(img, self.out_shape), {
            "scale_factors": (scale_factor_w, scale_factor_h)
        }

    def _det_long_max_rescale(self, img):
        height, width = img.shape[:2]
        scale_factor = min((self.out_shape[1] - 4) / height, (self.out_shape[0] - 4) / width)

        if scale_factor != 1.0:
            new_height, new_width = round(height * scale_factor), round(width * scale_factor)
            img = self.__rescale_img(img, (new_width, new_height))

        return img, {"scale_factors": (scale_factor, scale_factor)}

    def _bot_right_pad(self, img, pad_value):
        pad_height, pad_width = self.out_shape[1] - img.shape[0], self.out_shape[0] - img.shape[1]
        return cv2.copyMakeBorder(
            img, 0, pad_height, 0, pad_width, cv2.BORDER_CONSTANT, value=[pad_value] * img.shape[-1]
        ), {"padding": (0, pad_height, 0, pad_width)}

    def _center_pad(self, img, pad_value):
        pad_height, pad_width = self.out_shape[1] - img.shape[0], self.out_shape[0] - img.shape[1]
        pad_top, pad_left = pad_height // 2, pad_width // 2
        return cv2.copyMakeBorder(
            img,
            pad_top,
            pad_height - pad_top,
            pad_left,
            pad_width - pad_left,
            cv2.BORDER_CONSTANT,
            value=[pad_value] * img.shape[-1],
        ), {"padding": (pad_top, pad_height - pad_top, pad_left, pad_width - pad_left)}

    def _normalize(self, img, mean, std):
        return (img - np.asarray(mean)) / np.asarray(std), None

    def _call_fn(self, name):
        mapper = {
            "Standardize": self._standarize,
            "DetRescale": self._det_rescale,
            "DetLongMaxRescale": self._det_long_max_rescale,
            "BotRightPad": self._bot_right_pad,
            "CenterPad": self._center_pad,
            "Normalize": self._normalize,
        }
        return mapper[name]

    def __call__(self, img):
        img = img.copy()
        metadata = []
        for st in self.steps:
            if not st:
                continue
            name, kwargs = list(st.items())[0]
            img, meta = self._call_fn(name)(img, **kwargs) if kwargs else self._call_fn(name)(img)
            metadata.append(meta)

        img = cv2.dnn.blobFromImage(img, swapRB=True)
        return img, metadata


class Postprocessing:
    def __init__(self, steps, iou_tresh, score_tresh):
        self.steps = steps
        self.iou_tresh = iou_tresh
        self.score_tresh = score_tresh

    def _rescale_boxes(self, boxes, metadata):
        scale_factors_w, scale_factors_h = metadata["scale_factors"]
        boxes[:, [0, 2]] /= scale_factors_w
        boxes[:, [1, 3]] /= scale_factors_h
        return boxes

    def _shift_bboxes(self, boxes, metadata):
        pad_top, _, pad_left, _ = metadata["padding"]
        boxes[:, [0, 2]] -= pad_left
        boxes[:, [1, 3]] -= pad_top
        return boxes

    def _call_fn(self, name):
        mapper = {
            "DetRescale": self._rescale_boxes,
            "DetLongMaxRescale": self._rescale_boxes,
            "BotRightPad": self._shift_bboxes,
            "CenterPad": self._shift_bboxes,
            "Standardize": None,
            "Normalize": None,
        }
        return mapper[name]

    def __call__(self, outputs, metadata):
        boxes, raw_scores = outputs
        boxes = np.squeeze(boxes, 0)

        metadata = metadata.copy()
        for st in reversed(self.steps):
            if not st:
                continue
            name, _ = list(st.items())[0]
            meta = metadata.pop()
            if not self._call_fn(name):
                continue
            boxes = self._call_fn(name)(boxes, meta)

        # change xyxy to xywh
        boxes[:, 2] -= boxes[:, 0]
        boxes[:, 3] -= boxes[:, 1]

        scores = raw_scores.max(axis=2).flatten()
        classes = np.argmax(raw_scores, axis=2).flatten()
        return boxes, scores, classes
