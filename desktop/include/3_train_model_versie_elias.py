import os
import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers, models
import random

class Tracking:
    def __init__(self, image_dir, json_path, scaler=64):
        self.image_dir = image_dir
        self.json_path = json_path
        self.scaler = scaler
        self.scaler_height = int(scaler * (3 / 4))  # Adjusted to maintain 3:4 aspect ratio
        self.coordinates_data = self.load_json()
        self.model = None

    def load_json(self):
        with open(self.json_path, 'r') as f:
            return json.load(f)

    def load_data(self):
        boxes = []
        images = []
        for filename in os.listdir(self.image_dir):
            if filename.endswith('.jpg'):
                img_path = os.path.join(self.image_dir, filename)
                img = cv2.imread(img_path)
                if img is None:
                    print(f"Warning: Could not read image {img_path}")
                    continue
                img = cv2.resize(img, (self.scaler, self.scaler_height))  # Resize using scaler and scaler_height
                images.append(img)

                frame_name = filename.replace('.jpg', '.json')
                if frame_name in self.coordinates_data:
                    box = self.coordinates_data[frame_name]
                    try:
                        x = float(box['x'])
                        y = float(box['y'])
                        w = float(box['w'])
                        h = float(box['h'])
                        scaled_box = self.scale_bbox(x, y, w, h)
                        boxes.append(scaled_box)
                    except KeyError:
                        boxes.append([0.0, 0.0, 0.0, 0.0])
                else:
                    print(f"No coordinates found for frame {frame_name}")
        return np.array(images), np.array(boxes)

    def scale_bbox(self, x, y, w, h):
        scale_x = self.scaler / 640
        scale_y = self.scaler_height / 480  # Use scaler_height based on 3:4 aspect ratio
        new_x = x * scale_x
        new_y = y * scale_y
        new_width = w * scale_x
        new_height = h * scale_y
        return [new_x, new_y, new_width, new_height]

    def rescale_bbox(self, box, original_width, original_height):
        scale_x = original_width / self.scaler
        scale_y = original_height / self.scaler_height
        x, y, w, h = box
        new_x = x * scale_x
        new_y = y * scale_y
        new_width = w * scale_x
        new_height = h * scale_y
        return [new_x, new_y, new_width, new_height]

    def rescale_point(self, point, original_width, original_height):
        scale_x = original_width / self.scaler
        scale_y = original_height / self.scaler_height
        cx, cy = point
        new_cx = cx * scale_x
        new_cy = cy * scale_y
        return new_cx, new_cy

    def draw_bounding_box(self, img, box, color):
        if img is None or img.size == 0:
            raise ValueError("Invalid image provided")

        original_height, original_width, _ = img.shape
        scaled_box = self.rescale_bbox(box, original_width, original_height)

        # Rescale coordinates back to original image size
        x, y, w, h = map(int, scaled_box)

        # Draw bounding box directly on the image
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)

        return img

    def draw_middle_point(self, img, middle_point, color):
        if img is None or img.size == 0:
            raise ValueError("Invalid image provided")

        original_height, original_width, _ = img.shape
        scaled_point = self.rescale_point(middle_point, original_width, original_height)

        cx, cy = map(int, scaled_point)

        # Draw the middle point on the image
        cv2.circle(img, (cx, cy), radius=5, color=color, thickness=-1)

        return img

    def preprocess_data(self):
        images, boxes = self.load_data()
        images = images / 255.0
        return train_test_split(images, boxes, test_size=0.2, random_state=42)

    def build_model(self):
        self.model = models.Sequential([
            layers.Conv2D(16, (3, 3), activation='relu', input_shape=(self.scaler_height, self.scaler, 3)),
            layers.MaxPooling2D((2, 2)),

            layers.Conv2D(32, (3, 3), activation='relu'),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.5),

            layers.Flatten(),

            # Dense layers for localization
            layers.Dense(128),
            layers.Dense(128),
            

            layers.Dense(4)
        ])

        self.model.compile(optimizer='adam',
                           loss='mean_squared_error',
                           metrics=['accuracy'])

    def train_model(self, images_train, images_val, boxes_train, boxes_val, epochs=20):
        self.model.fit(images_train, boxes_train, epochs=epochs,
                       validation_data=(images_val, boxes_val))

    def predict_bounding_box(self, img):
        if img is None or img.size == 0:
            raise ValueError("Invalid image provided")

        img_resized = cv2.resize(img, (self.scaler, self.scaler_height))
        img_normalized = img_resized / 255.0
        img_expanded = np.expand_dims(img_normalized, axis=0)

        predicted_box = self.model.predict(img_expanded)
        return predicted_box[0]

    def visualize_bounding_boxes(self, img_path):
        example_img = cv2.imread(img_path)
        if example_img is not None:
            actual_box = self.get_actual_bounding_box(img_path)
            predicted_box = self.predict_bounding_box(example_img)

            mid_act = self.calculate_middle_point(actual_box)
            mid_pred = self.calculate_middle_point(predicted_box)
            difference = np.linalg.norm(np.array(mid_act) - np.array(mid_pred))
            average_diff = np.mean(difference)

            print("Middle point actual: ", mid_act)
            print("Middle point prediction: ", mid_pred)
            print("Difference: ", difference)
            print(average_diff)

            img_with_actual_box = self.draw_bounding_box(example_img.copy(), actual_box, (0, 255, 0))
            img_with_predicted_box = self.draw_bounding_box(img_with_actual_box, predicted_box, (0, 0, 255))

            # Draw middle points
            img_with_actual_middle = self.draw_middle_point(img_with_predicted_box, mid_act, (0, 255, 0))
            img_with_predicted_middle = self.draw_middle_point(img_with_actual_middle, mid_pred, (0, 0, 255))

            plt.imshow(cv2.cvtColor(img_with_predicted_middle, cv2.COLOR_BGR2RGB))

            actual_patch = plt.Line2D([0], [0], color='g', linewidth=2, label='Actual Box')
            predicted_patch = plt.Line2D([0], [0], color='r', linewidth=2, label='Predicted Box')
            
            plt.legend(handles=[actual_patch, predicted_patch], loc='lower right')

            plt.show()
        else:
            print(f"Could not read example image at {img_path}")

    def get_actual_bounding_box(self, img_path):
        frame_name = os.path.basename(img_path).replace('.jpg', '.json')
        if frame_name in self.coordinates_data:
            box = self.coordinates_data[frame_name]
            x = float(box['x'])
            y = float(box['y'])
            w = float(box['w'])
            h = float(box['h'])
            return self.scale_bbox(x, y, w, h)
        else:
            return [0.0, 0.0, 0.0, 0.0]

    def calculate_middle_point(self, box):
        x, y, w, h = box
        cx = x + w / 2
        cy = y + h / 2
        return cx, cy


if __name__ == "__main__":
    image_dir = "data/traindata"
    json_path = "data/validatiedata/combined.json"
    scaler = 64
    epochs = 1500

    tracking = Tracking(image_dir, json_path, scaler)
    images_train, images_val, boxes_train, boxes_val = tracking.preprocess_data()
    tracking.build_model()
    tracking.train_model(images_train, images_val, boxes_train, boxes_val, epochs=epochs)

    # Choose 8 random image paths
    random_image_paths = random.sample(os.listdir(image_dir), 50)
    random_image_paths = [os.path.join(image_dir, img_path) for img_path in random_image_paths if img_path.endswith('.jpg')]

    for img_path in random_image_paths:
        tracking.visualize_bounding_boxes(img_path)