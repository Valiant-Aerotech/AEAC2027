"""Shared detection defaults."""

# Nominal capture resolution the detectors were tuned against. Frames of other
# sizes are scaled, not rejected.
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080

DEFAULT_CONFIDENCE_THRESHOLD = 0.35

# Labels the 2027 missions look for. Detector backends set these on Detection
# objects; nothing below the mission layer attaches meaning to them.
LABEL_DEER = "deer"
LABEL_EAR_TAG = "ear_tag"
LABEL_LEG_BAND = "leg_band"
LABEL_LANDING_PAD = "landing_pad"
LABEL_SAMPLE = "sample"
