# Third-party models

## Room Segmentation

AutoBOQ can optionally use the public Roboflow Universe model `room-segmentation-o7iga/4` as supporting evidence for room detection. The model is published by Nirwana under the Creative Commons Attribution 4.0 International (CC BY 4.0) license.

The model output is never treated as the final quantity boundary automatically. AutoBOQ keeps wall-derived inner-face geometry as the primary result, compares it with model suggestions, and requires review when the results differ.

Model page: `https://universe.roboflow.com/nirwana/room-segmentation-o7iga`
License: `https://creativecommons.org/licenses/by/4.0/`
