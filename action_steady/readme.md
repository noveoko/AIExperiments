# ActionSteady

Here’s a solid **README.md** you can drop into your project root:

---

# ActionSteady

**Intelligent Video Stabilization for High-Motion Footage**

ActionSteady is a modular Python-based video stabilization system designed for challenging scenarios like:

* Running (chest-mounted cameras)
* Action cams (GoPro-style footage)
* High-frequency jitter and bounce
* Foreground-heavy scenes

It combines classical computer vision with optional IMU (gyro) fusion and advanced techniques inspired by tools like Gyroflow.

---

## 🚀 Features

### Core Stabilization

* Optical flow-based motion estimation
* Affine transform modeling (dx, dy, rotation)
* Trajectory accumulation and correction

### Advanced Stabilization

* ✅ Kalman filter smoothing (adaptive noise handling)
* ✅ Motion-energy adaptive smoothing
* ✅ Quaternion-based rotation (no gimbal lock)
* ✅ Gyro (IMU) integration and fusion
* ✅ Automatic gyro/video time synchronization

### Pro-Level Enhancements

* ✅ Rolling shutter correction (row-wise warping)
* ✅ Dynamic cropping (auto zoom to remove black borders)

---

## 📁 Project Structure

```
actionsteady/
│
├── stabilize.py          # Entry point (currently minimal)
│
├── core/
│   ├── quaternion.py     # Quaternion math & gyro integration
│   ├── sync.py           # Gyro-video time alignment
│   ├── kalman.py         # Kalman smoothing
│   ├── rolling_shutter.py# Row-wise warping
│   ├── crop.py           # Dynamic cropping
│
```

---

## ⚙️ Installation

### Requirements

* Python 3.10+
* OpenCV
* NumPy

Install dependencies:

```bash
pip install numpy opencv-python
```

---

## 📦 Usage (Current State)

Right now, the project provides **core modules**, not a fully wired CLI.

Basic test:

```bash
python stabilize.py
```

Output:

```
ActionSteady ready. Integrate modules as needed.
```

---

## 🧠 How It Works

### 1. Motion Estimation

Camera motion is estimated between frames using optical flow and converted into transforms:

```
T = [dx, dy, da]
```

---

### 2. Trajectory Modeling

```
trajectory[t] = Σ transforms
```

---

### 3. Stabilization Strategy

#### Without Gyro

* Smooth trajectory (Kalman or adaptive)
* Apply corrective transforms

#### With Gyro

* Integrate gyro → quaternion orientation
* Synchronize with video
* Fuse gyro + vision signals

---

### 4. Rolling Shutter Correction

Each row of the frame is warped differently:

```
top rows → earlier time
bottom rows → later time
```

This removes the “jello effect” common in action cameras.

---

### 5. Dynamic Cropping

Automatically zooms to remove black borders caused by stabilization:

* Estimates maximum displacement
* Applies safe crop factor
* Rescales to original resolution

---

## 📊 Current Capabilities

| Feature                    | Status                       |
| -------------------------- | ---------------------------- |
| Optical flow stabilization | ⚠️ Partial (not wired)       |
| Kalman smoothing           | ✅ Implemented                |
| Gyro integration           | ✅ Implemented                |
| Time sync                  | ✅ Implemented                |
| Rolling shutter correction | ✅ Implemented                |
| CLI tool                   | ❌ Not yet                    |
| YOLO masking               | ❌ Not included in this build |

---

## ⚠️ Limitations

This is not yet full production-level stabilization. Missing:

* Lens distortion correction
* Camera intrinsics calibration
* Mesh-based warping (non-affine)
* Real-time processing
* Full pipeline integration
* CLI interface
* Video encoding (FFmpeg)

---

## 🛠️ Next Steps

To reach full production quality:

1. Add full pipeline wiring (frames → transforms → output)
2. Integrate YOLO masking
3. Add CLI interface
4. Add FFmpeg video export
5. Add lens calibration
6. Optimize with GPU acceleration

---

## 🔬 Design Philosophy

* Modular and transparent (no black-box magic)
* Physics-informed stabilization (IMU + vision)
* Extensible for research and experimentation

---

## 🤝 Contributing

Feel free to extend:

* Feature tracking
* Deep optical flow (RAFT)
* Real-time preview
* GUI interface

---

## 📜 License

Open-source (choose your preferred license)

---

## 💬 Final Note

This project is a **foundation for a high-end stabilizer**, not just a script.

If you continue building it out, you can reach parity with tools like Gyroflow—and even go beyond.

---

If you want, I can next:

* wire everything into a **fully working CLI tool**
* or add **YOLO masking + POV mode (your original spec)**
