#pragma once

#include <vector>
#include <opencv2/opencv.hpp>
#include <opencv2/dnn.hpp>

#include "draw.hpp"

struct PreprocessingMetadata
{
    float scaleFactor;
    std::vector<int> padding;
};

class YoloNAS
{
private:
    int netInputShape[4] = {1, 3, 0, 0};
    float scoreTresh;
    float iouTresh;
    void warmup(int round);
    Colors colors;

public:
    cv::dnn::Net net;
    std::vector<int> imgSize;
    YoloNAS(std::string netPath, std::vector<int> imgsz, bool cuda, float scoreTresh, float iouTresh);
    PreprocessingMetadata preprocess(cv::Mat &source, cv::Mat &dst);
    void postprocess(std::vector<std::vector<cv::Mat>> &out,
                     std::vector<cv::Rect> &boxes,
                     std::vector<int> &labels,
                     std::vector<float> &scores,
                     std::vector<int> &selectedIDX,
                     PreprocessingMetadata &scaleFactor);
    void predict(cv::Mat &img);
};