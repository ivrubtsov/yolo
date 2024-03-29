from ultralytics import YOLO
import cv2
import os
import time
import math
import urllib.request

model = YOLO("yolov8s.pt")  # load a pretrained model (recommended for training)

# Constants:
FILE_TYPE_VIDEO = 'video'
FILE_TYPE_IMAGE = 'image'
FILE_SOURCE_URL = 'url'
FILE_SOURCE_PATH = 'path'
FILE_SOURCE_S3 = 's3'

# Environment variables:
TMP_DIR = os.getenv('TMP_DIR')
if not TMP_DIR:
    TMP_DIR = '/tmp'
MODEL_STEP_INITIAL = os.getenv('MODEL_STEP_INITIAL')
if not MODEL_STEP_INITIAL:
    MODEL_STEP_INITIAL = 1
MODEL_SMOOTH_ACCELERATION = os.getenv('MODEL_SMOOTH_ACCELERATION')
if not MODEL_SMOOTH_ACCELERATION:
    MODEL_SMOOTH_ACCELERATION = 3
MODEL_CONFIDENCE = os.getenv('MODEL_CONFIDENCE')
if not MODEL_CONFIDENCE:
    MODEL_CONFIDENCE = 0.5
MODEL_INTERSECTION = os.getenv('MODEL_INTERSECTION')
if not MODEL_INTERSECTION:
    MODEL_INTERSECTION = 0.9
MODEL_SMOOTH_DEGRADATION = os.getenv('MODEL_SMOOTH_DEGRADATION')
if not MODEL_SMOOTH_DEGRADATION:
    MODEL_SMOOTH_DEGRADATION = 10

S3_BUCKET = os.getenv('S3_BUCKET')
S3_KEY = os.getenv('S3_KEY')
S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
S3_REGION = os.getenv('S3_REGION')
if not S3_REGION:
    S3_REGION = "eu-west-2"

# For all coords:
# 0 - left
# 1 - top
# 2 - right
# 3 - bottom
def tracker(fileType, fileSource, fileAddress, cropCoords):
    fileName, fileExtension = os.path.splitext(fileAddress)
    if fileSource==FILE_SOURCE_URL:
        # Downloading the file from URL, creating an unique name with a timestamp
        fileOrigin = TMP_DIR+'/raw'+fileExtension
        if not os.path.exists(TMP_DIR):
            os.makedirs(TMP_DIR)
        try:
            urllib.request.urlretrieve(fileAddress, fileOrigin)
        except Exception as e:
            return('Can\'t download file from URL, error: '+e)

    elif fileSource==FILE_SOURCE_PATH:
        if not os.path.exists(fileAddress):
            return('Source file doesn\'t exist')
        else:
            fileOrigin = fileAddress
    
    elif fileSource==FILE_SOURCE_S3:
        fileOrigin = TMP_DIR+'/raw'+fileExtension
        if not os.path.exists(TMP_DIR):
            os.makedirs(TMP_DIR)
        try:
            s3_download_file(fileOrigin, fileAddress)
        except Exception as e:
            return('Can\'t download file from S3, error: '+e)
    else:
        return("Source error")

    if fileType==FILE_TYPE_VIDEO:
        fileTarget = TMP_DIR+'/result.mp4'
        # Start processing video file
        result = trackVideo(fileOrigin, fileTarget, cropCoords)
        return result

    elif fileType==FILE_TYPE_IMAGE:
        fileTarget = TMP_DIR+'/result.jpg'
        # Start processing image file
        result = trackImage(fileOrigin, fileTarget, cropCoords)
        return result

    else:
        return("File type error")

    return("Tracking is over, but there is no result")

def trackVideo(fileSource, fileTarget, cropCoords):
    tic = time.perf_counter()
    vidCapture = cv2.VideoCapture(fileSource)
    fps = vidCapture.get(cv2.CAP_PROP_FPS)
    totalFrames = vidCapture.get(cv2.CAP_PROP_FRAME_COUNT)
    print("Processing video")
    print("Total frames: "+str(totalFrames))
    width = int(vidCapture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vidCapture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not cropCoords:
        [box_left, box_top, box_right, box_bottom] = [0, 0, width, height]
    else:
        [box_left, box_top, box_right, box_bottom] = cropCoords
        if (box_left<0):
            box_left=0
        if (box_top<0):
            box_top=0
        if (box_right)>width:
            box_right=width
        if (box_bottom>height):
            box_bottom=height
    lastCoords = [box_left, box_top, box_right, box_bottom]
    lastBoxCoords = lastCoords
    box_width = box_right-box_left
    box_height = box_bottom-box_top
    outputWriter = []
    outputWriter.append(cv2.VideoWriter(fileTarget, cv2.VideoWriter_fourcc(*'MPEG'), fps, (box_width, box_height)))

    # Initialization of smoothing
    stepLevelX = MODEL_STEP_INITIAL
    stepLevelY = MODEL_STEP_INITIAL
    directionX = 0
    directionY = 0

    frameCounter = 1
    while True:

        r, im = vidCapture.read()

        if not r:
            print("Video Finished!")
            break
        
        print("Frame: "+str(frameCounter))
        frameCounter = frameCounter+1
        
        results = model.predict(source=im, conf=MODEL_CONFIDENCE, iou=MODEL_INTERSECTION, show=False, hide_labels=True, hide_conf=True, vid_stride=False, visualize=False)
        boxes = results[0].boxes
        box = closestBox(boxes, boxCenter(lastBoxCoords))  # returns the best box
        lastBoxCoords = box.xyxy[0].numpy().astype(int)
        newCoords = adjustBoxSize(box.xyxy[0].numpy().astype(int), box_width, box_height)
        [newCoords, stepLevelX, stepLevelY, directionX, directionY] = smoothMove(newCoords, lastCoords, stepLevelX, stepLevelY, directionX, directionY)
        newCoords = adjustBoundaries(newCoords,[width, height]) # don't allow to get the crop area go out of edges
        [box_left, box_top, box_right, box_bottom] = newCoords
        #print("left=",box_left," top=",box_top,"right=",box_right,"bottom=",box_bottom)
        imCropped = im[box_top:box_bottom, box_left:box_right]
        outputWriter[0].write(imCropped)
        lastCoords = newCoords

    outputWriter[0].release()

    #compressedVideoOutput = str(vid_path.split('.mp4')[0]) + '_compressed.mp4'
    #command = 'ffmpeg -i {} -vcodec libx264 -y -an -crf 28 {}'.format(vid_path, compressedVideoOutput)
    #subprocess.call(command, shell=platform.system() != 'Windows')

    toc = time.perf_counter()
    processingTimeInfo = f"Processed time {toc - tic:0.4f} seconds"
    print(processingTimeInfo)
    return "Processed the video, file is saved at '"+fileTarget+"'"

def trackImage(fileSource, fileTarget, cropCoords):
    im = cv2.imread(fileSource)
    height, width = im.shape[:2]
    results = model.predict(source=im,iou=0.1)
    boxes = results[0].boxes
    if not cropCoords:
        [box_left, box_top, box_right, box_bottom] = [0, 0, width, height]
    else:
        [box_left, box_top, box_right, box_bottom] = cropCoords
        if (box_left<0):
            box_left=0
        if (box_top<0):
            box_top=0
        if (box_right)>width:
            box_right=width
        if (box_bottom>height):
            box_bottom=height
    box_width = box_right-box_left
    box_height = box_bottom-box_top
    box = closestBox(boxes, boxCenter(cropCoords))  # returns the best box
    [box_left, box_top, box_right, box_bottom] = adjustBoxSize(box.xyxy[0].numpy().astype(int), box_width, box_height)
    [box_left, box_top, box_right, box_bottom] = adjustBoundaries([box_left, box_top, box_right, box_bottom],[width, height])
    im_cropped = im[box_top:box_bottom, box_left:box_right]
    cv2.imwrite(fileTarget,im_cropped)
    return "Processed the image, file is saved at '"+fileTarget+"'"

# Return the coordinates of a center point [x,y]
def boxCenter(coords):
    [left, top, right, bottom] = coords
    return [(left+right)/2,(top+bottom)/2]

# If the box is out of the boundaries we move the box to an edge
def adjustBoundaries(coords,screen):
    [left, top, right, bottom] = coords
    [width, height]=screen
    if left<0:
        right=right-left
        left=0
    if top<0:
        bottom=bottom-top
        top=0
    if right>width:
        left=left-(right-width)
        right=width
    if bottom>height:
        top=top-(bottom-height)
        bottom=height
    return [round(left), round(top), round(right), round(bottom)]

def closestBox(boxes, center):
    distance = []
    for box in boxes:
        boxCent = boxCenter(box.xyxy[0].numpy().astype(int))
        distance.append(calculateDistanceBetweenCenters(boxCent,center))
    return boxes[distance.index(min(distance))]

def calculateDistanceBetweenCenters(coord1,coord2):
    return math.dist(coord1, coord2)

def adjustBoxSize(coords, box_width, box_height):
    [centerX, centerY] = boxCenter(coords)
    return [centerX-box_width/2, centerY-box_height/2, centerX+box_width/2, centerY+box_height/2]

def smoothMove(newCoords, lastCoords, stepLevelX, stepLevelY, directionX, directionY):
    [newCenterX, newCenterY] = boxCenter(newCoords)
    [oldCenterX, oldCenterY] = boxCenter(lastCoords)
    newChangeX = newCenterX-oldCenterX
    newChangeY = newCenterY-oldCenterY

    if directionX==0:
        if newChangeX>0:
            directionX = 1
        elif newChangeX<0:
            directionX = -1
        stepLevelX = MODEL_STEP_INITIAL
    
    if directionY==0:
        if newChangeY>0:
            directionY = 1
        elif newChangeY<0:
            directionY = -1
        stepLevelY = MODEL_STEP_INITIAL

    if (directionX==1 and newChangeX>0):
        if (newChangeX>stepLevelX):
            stepLevelX = (stepLevelX)*MODEL_SMOOTH_ACCELERATION
        else:
            stepLevelX = round(stepLevelX/MODEL_SMOOTH_ACCELERATION)
    elif (directionX==-1 and newChangeX<0):
        if (abs(newChangeX)>stepLevelX):
            stepLevelX = (stepLevelX)*MODEL_SMOOTH_ACCELERATION
        else:
            stepLevelX = round(stepLevelX/MODEL_SMOOTH_ACCELERATION)
    else:
        stepLevelX = round(stepLevelX/MODEL_SMOOTH_ACCELERATION)

    if (directionY==1 and newChangeY>0):
        if (newChangeY>stepLevelY):
            stepLevelY = (stepLevelY)*MODEL_SMOOTH_ACCELERATION
        else:
            stepLevelY = round(stepLevelY/MODEL_SMOOTH_ACCELERATION)
    elif (directionY==-1 and newChangeY<0):
        if (abs(newChangeY)>stepLevelY):
            stepLevelY = (stepLevelY)*MODEL_SMOOTH_ACCELERATION
        else:
            stepLevelY = round(stepLevelY/MODEL_SMOOTH_ACCELERATION)
    else:
        stepLevelY = round(stepLevelY/MODEL_SMOOTH_ACCELERATION)

    if stepLevelX<1:
        directionX = 0

    if stepLevelY<1:
        directionY = 0
    
    [box_left, box_top, box_right, box_bottom] = lastCoords
    newCoords = [box_left+stepLevelX*directionX/MODEL_SMOOTH_DEGRADATION, box_top+stepLevelY*directionY/MODEL_SMOOTH_DEGRADATION, box_right+stepLevelX*directionX/MODEL_SMOOTH_DEGRADATION, box_bottom+stepLevelY*directionY/MODEL_SMOOTH_DEGRADATION]

    return [newCoords, stepLevelX, stepLevelY, directionX, directionY]

def s3_download_file(file, downloadFileUrl):
    import boto3
    s3 = boto3.client(
        "s3",
        aws_access_key_id=S3_KEY,
        region_name=S3_REGION,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    )
    tic = time.perf_counter()
    print("Downloading file ", file, " from S3 Bucket ", S3_BUCKET, ", URL: ", downloadFileUrl)
    downloadedFile = s3.download_file(
        S3_BUCKET,
        downloadFileUrl,
        file,
    )
    toc = time.perf_counter()
    print(f"Download time {toc - tic:0.4f} seconds")
    return downloadedFile

