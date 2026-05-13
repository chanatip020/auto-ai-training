Act as a senior full-stack AI software architect.

I want to build an AI Auto Training Platform for computer vision model training.

Project goal:
Create software that allows users to create projects, upload datasets, import datasets from CVAT API, analyze dataset quality, automatically convert folder structures to match selected model formats, recommend dataset improvements, tune training parameters, train models, and monitor progress for each project.

Main features:

1. Project Management
- User can create a new project
- Each project has project name, description, model type, task type, dataset version, training status, and created date
- Each project can contain multiple datasets
- Each project can contain multiple training jobs
- Show project dashboard
- Show progress of each project
- Show current step: created, dataset uploaded, dataset analyzed, ready for training, training, completed, failed

2. Dataset Upload
- Upload images and labels
- Support ZIP upload
- Support manual dataset upload from web UI
- Validate dataset structure
- Store dataset under each project
- Show dataset upload progress
- Show dataset summary after upload

3. CVAT API Integration
- Allow users to connect to CVAT server
- Import dataset from CVAT project or CVAT task using CVAT API
- Support CVAT authentication
- List available CVAT projects and tasks
- Select CVAT task/project and import annotations
- Export CVAT annotation format into YOLO format
- Save imported CVAT dataset into the selected project
- Show CVAT import progress
- Handle CVAT API error and retry

4. Model Selection
- Allow users to select model type, such as YOLO
- Support future models such as classification, segmentation, and detection models
- Automatically prepare dataset format based on selected model

5. Dataset Format Conversion
- Convert uploaded dataset folder structure to YOLO format
- Generate data.yaml automatically
- Split dataset into train, validation, and test folders
- Default split ratio: 70% train, 20% validation, 10% test
- Save each converted dataset as a dataset version

6. Dataset Analysis
- Count total images and labels
- Check missing labels
- Check empty labels
- Check class imbalance
- Check image resolution
- Detect duplicate images
- Detect corrupted images
- Show class distribution
- Show dataset health score

7. Dataset Recommendation
- Recommend if more images are needed
- Recommend if some classes need more samples
- Recommend whether augmentation is needed
- Recommend suitable image size
- Recommend suitable train/validation/test split
- Recommend if dataset is ready for training or not

8. Training Parameter Recommendation
- Recommend model size, such as YOLO nano, small, medium
- Recommend epochs, batch size, image size, learning rate, optimizer, and augmentation settings
- Explain why each parameter is recommended

9. Training Pipeline
- Start training from each project
- Select dataset version before training
- Show training progress per project
- Show current epoch, total epochs, loss, mAP, precision, recall
- Show logs in real time
- Allow stop training
- Save training result history
- Save best model weights
- Show metrics such as mAP, precision, recall, loss, and confusion matrix

10. Project Progress Dashboard
- Show all projects in a dashboard
- Show project status
- Show dataset upload progress
- Show CVAT import progress
- Show dataset analysis progress
- Show training progress
- Show latest model performance
- Show failed projects with error message

11. Full-Stack Architecture
- Frontend: React + Tailwind CSS
- Backend: FastAPI
- Database: PostgreSQL or Supabase
- File Storage: local storage, MinIO, or S3-compatible storage
- Training Engine: Python + Ultralytics YOLO
- CVAT Integration: CVAT REST API
- Background Jobs: Celery, Redis, or FastAPI BackgroundTasks
- Real-time Progress: WebSocket or Server-Sent Events
- Optional: Docker deployment

Please design:
- System architecture
- Database schema
- API endpoints
- Folder structure
- Frontend pages
- Backend services
- Dataset processing workflow
- CVAT import workflow
- Training workflow
- Project progress workflow
- Recommended tech stack
- Step-by-step development roadmap

Make the answer practical, clean, scalable, and suitable for real production software.