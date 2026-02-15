const WEB_DEFAULTS = {
  borderCleanMaxSide: 2400,
  borderBandRatio: 0.03,
  borderBandMin: 24,
  bboxProjRatio: 0.002,
  splitPercentile: 24,
  a4Ratio: 297.0 / 210.0,
};

const appState = {
  cvReady: false,
  sourceCanvas: null,
  sourceName: "",
  sourceOriginalSize: null,
  scaleFromOriginal: 1,
  result: null,
};

const dom = {};

function byId(id) {
  return document.getElementById(id);
}

function initDomRefs() {
  dom.fileInput = byId("fileInput");
  dom.optDetectMaxSide = byId("optDetectMaxSide");
  dom.optPaddingRatio = byId("optPaddingRatio");
  dom.optMinCoverRatio = byId("optMinCoverRatio");
  dom.optMarginMm = byId("optMarginMm");
  dom.optJpegQuality = byId("optJpegQuality");
  dom.optWebMaxSide = byId("optWebMaxSide");

  dom.runBtn = byId("runBtn");
  dom.downloadBinaryBtn = byId("downloadBinaryBtn");
  dom.downloadBoxBtn = byId("downloadBoxBtn");
  dom.downloadPdfBtn = byId("downloadPdfBtn");

  dom.runtimeInfo = byId("runtimeInfo");
  dom.logBox = byId("logBox");

  dom.originalCanvas = byId("originalCanvas");
  dom.binaryCanvas = byId("binaryCanvas");
  dom.boxCanvas = byId("boxCanvas");
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function setRuntime(message, isError = false) {
  if (!dom.runtimeInfo) {
    return;
  }
  dom.runtimeInfo.textContent = `状态：${message}`;
  dom.runtimeInfo.style.color = isError ? "#a73220" : "";
}

function appendLog(message) {
  if (!dom.logBox) {
    return;
  }
  const now = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  dom.logBox.textContent += `\n[${now}] ${message}`;
  dom.logBox.scrollTop = dom.logBox.scrollHeight;
}

function resetPreviewCanvas(canvas) {
  canvas.width = 4;
  canvas.height = 4;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, 4, 4);
}

function drawPreviewFromCanvas(srcCanvas, targetCanvas) {
  const maxW = 1300;
  const maxH = 520;
  const scale = Math.min(maxW / srcCanvas.width, maxH / srcCanvas.height, 1);
  const w = Math.max(1, Math.round(srcCanvas.width * scale));
  const h = Math.max(1, Math.round(srcCanvas.height * scale));
  targetCanvas.width = w;
  targetCanvas.height = h;
  const ctx = targetCanvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  ctx.drawImage(srcCanvas, 0, 0, w, h);
}

function parseOptions() {
  const detectMaxSide = clamp(Number(dom.optDetectMaxSide.value || 2400), 400, 6000);
  const paddingRatio = clamp(Number(dom.optPaddingRatio.value || 0.03), 0, 0.2);
  const minCoverRatio = clamp(Number(dom.optMinCoverRatio.value || 0.85), 0.5, 1.0);
  const marginMm = clamp(Number(dom.optMarginMm.value || 5), 0, 30);
  const jpegQuality = clamp(Number(dom.optJpegQuality.value || 90), 40, 100);
  const webMaxSide = clamp(Number(dom.optWebMaxSide.value || 16384), 2000, 20000);
  return {
    detectMaxSide,
    paddingRatio,
    minCoverRatio,
    marginMm,
    jpegQuality,
    webMaxSide,
  };
}

function setDownloadButtonsEnabled(binaryEnabled, pdfEnabled) {
  dom.downloadBinaryBtn.disabled = !binaryEnabled;
  dom.downloadBoxBtn.disabled = !binaryEnabled;
  dom.downloadPdfBtn.disabled = !pdfEnabled;
}

function safeBaseName(name) {
  const trimmed = (name || "inkcrop").replace(/\.[^.]+$/, "");
  return trimmed.replace(/[\\/:*?"<>|]+/g, "_");
}

function downloadCanvas(canvas, filename) {
  const dataUrl = canvas.toDataURL("image/png");
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  a.click();
}

async function ensureCvReady(timeoutMs = 60000) {
  if (appState.cvReady && window.cv && window.cv.Mat) {
    return;
  }

  const start = performance.now();
  setRuntime("等待 OpenCV.js 初始化...");

  while (performance.now() - start < timeoutMs) {
    if (window.cv && window.cv.Mat) {
      appState.cvReady = true;
      setRuntime("OpenCV.js 已就绪");
      appendLog("OpenCV.js 初始化完成");
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 120));
  }

  throw new Error("OpenCV.js 加载超时，请检查网络后刷新页面。");
}

async function loadSelectedImage() {
  const file = dom.fileInput.files && dom.fileInput.files[0];
  if (!file) {
    throw new Error("请先选择图片文件。");
  }
  const options = parseOptions();

  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.decoding = "async";
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error("图片解码失败。"));
      image.src = objectUrl;
    });

    const srcW = image.naturalWidth;
    const srcH = image.naturalHeight;
    const maxSide = Math.max(srcW, srcH);
    const scale = maxSide > options.webMaxSide ? options.webMaxSide / maxSide : 1;
    const targetW = Math.max(1, Math.round(srcW * scale));
    const targetH = Math.max(1, Math.round(srcH * scale));

    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(image, 0, 0, targetW, targetH);

    appState.sourceCanvas = canvas;
    appState.sourceName = file.name;
    appState.sourceOriginalSize = { width: srcW, height: srcH };
    appState.scaleFromOriginal = scale;

    drawPreviewFromCanvas(canvas, dom.originalCanvas);
    resetPreviewCanvas(dom.binaryCanvas);
    resetPreviewCanvas(dom.boxCanvas);
    setDownloadButtonsEnabled(false, false);
    appState.result = null;

    if (scale < 1) {
      appendLog(
        `输入图过大，已自动缩图到 ${targetW}x${targetH}（原图 ${srcW}x${srcH}, scale=${scale.toFixed(4)}）`
      );
    } else {
      appendLog(`输入图加载完成：${targetW}x${targetH}`);
    }
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function matFromInk(binaryMat, inkValue) {
  const mask = new cv.Mat();
  if (inkValue === 255) {
    binaryMat.copyTo(mask);
  } else {
    cv.bitwise_not(binaryMat, mask);
  }
  return mask;
}

function getInkInfo(binaryMat) {
  const whitePixels = cv.countNonZero(binaryMat);
  const blackPixels = binaryMat.rows * binaryMat.cols - whitePixels;
  const inkValue = whitePixels <= blackPixels ? 255 : 0;
  return {
    whitePixels,
    blackPixels,
    inkValue,
  };
}

function reduceCounts(maskMat) {
  const rowSum = new cv.Mat();
  const colSum = new cv.Mat();
  cv.reduce(maskMat, rowSum, 1, cv.REDUCE_SUM, cv.CV_32S);
  cv.reduce(maskMat, colSum, 0, cv.REDUCE_SUM, cv.CV_32S);

  const rowCounts = new Array(maskMat.rows);
  const colCounts = new Array(maskMat.cols);
  for (let r = 0; r < maskMat.rows; r += 1) {
    rowCounts[r] = Math.round(rowSum.intPtr(r, 0)[0] / 255);
  }
  for (let c = 0; c < maskMat.cols; c += 1) {
    colCounts[c] = Math.round(colSum.intPtr(0, c)[0] / 255);
  }
  rowSum.delete();
  colSum.delete();
  return { rowCounts, colCounts };
}

function firstLastAbove(arr, threshold) {
  let first = -1;
  let last = -1;
  for (let i = 0; i < arr.length; i += 1) {
    if (arr[i] >= threshold) {
      first = i;
      break;
    }
  }
  if (first < 0) {
    return null;
  }
  for (let i = arr.length - 1; i >= 0; i -= 1) {
    if (arr[i] >= threshold) {
      last = i;
      break;
    }
  }
  if (last < 0) {
    return null;
  }
  return [first, last];
}

function smoothProjection(counts) {
  const n = counts.length;
  let k = Math.max(5, Math.round(n * 0.005));
  if (k % 2 === 0) {
    k += 1;
  }
  const half = Math.floor(k / 2);
  const prefix = new Float64Array(n + 1);
  for (let i = 0; i < n; i += 1) {
    prefix[i + 1] = prefix[i] + counts[i];
  }
  const out = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const left = Math.max(0, i - half);
    const right = Math.min(n - 1, i + half);
    const sum = prefix[right + 1] - prefix[left];
    out[i] = sum / (right - left + 1);
  }
  return out;
}

function projectionBounds(counts, highThresh, lowThresh) {
  const smooth = smoothProjection(counts);
  let run = firstLastAbove(smooth, highThresh);
  if (!run) {
    run = firstLastAbove(smooth, lowThresh);
  }
  return run;
}

function percentile(values, pct) {
  if (!values || values.length === 0) {
    return 0;
  }
  const arr = Array.from(values).sort((a, b) => a - b);
  const idx = clamp(Math.round((pct / 100) * (arr.length - 1)), 0, arr.length - 1);
  return arr[idx];
}

function removeBorderConnectedInk(binaryMat) {
  const inkInfo = getInkInfo(binaryMat);
  const inkMask = matFromInk(binaryMat, inkInfo.inkValue);
  const h = inkMask.rows;
  const w = inkMask.cols;
  const longSide = Math.max(h, w);

  let scale = 1.0;
  let inkSmall = inkMask;
  let ownSmall = false;
  if (longSide > WEB_DEFAULTS.borderCleanMaxSide) {
    scale = WEB_DEFAULTS.borderCleanMaxSide / longSide;
    const smallW = Math.max(1, Math.round(w * scale));
    const smallH = Math.max(1, Math.round(h * scale));
    inkSmall = new cv.Mat();
    cv.resize(inkMask, inkSmall, new cv.Size(smallW, smallH), 0, 0, cv.INTER_NEAREST);
    ownSmall = true;
  }

  const smallW = inkSmall.cols;
  const smallH = inkSmall.rows;
  const borderBandSmall = Math.max(
    WEB_DEFAULTS.borderBandMin,
    Math.round(Math.min(smallH, smallW) * WEB_DEFAULTS.borderBandRatio)
  );

  const labels = new cv.Mat();
  const stats = new cv.Mat();
  const centroids = new cv.Mat();
  const numLabels = cv.connectedComponentsWithStats(
    inkSmall,
    labels,
    stats,
    centroids,
    8,
    cv.CV_32S
  );

  const removeLabel = new Uint8Array(numLabels);
  for (let i = 1; i < numLabels; i += 1) {
    const left = stats.intPtr(i, cv.CC_STAT_LEFT)[0];
    const top = stats.intPtr(i, cv.CC_STAT_TOP)[0];
    const width = stats.intPtr(i, cv.CC_STAT_WIDTH)[0];
    const height = stats.intPtr(i, cv.CC_STAT_HEIGHT)[0];
    const right = left + width - 1;
    const bottom = top + height - 1;

    const touchesBorder = left <= 0 || top <= 0 || right >= smallW - 1 || bottom >= smallH - 1;
    if (!touchesBorder) {
      continue;
    }
    const inEdgeBand =
      left < borderBandSmall ||
      top < borderBandSmall ||
      right >= smallW - borderBandSmall ||
      bottom >= smallH - borderBandSmall;
    if (inEdgeBand) {
      removeLabel[i] = 1;
    }
  }

  const labelsData = labels.data32S;
  const removeData = new Uint8Array(labelsData.length);
  for (let i = 0; i < labelsData.length; i += 1) {
    const labelId = labelsData[i];
    if (labelId > 0 && removeLabel[labelId]) {
      removeData[i] = 255;
    }
  }

  let removeSmall = cv.matFromArray(smallH, smallW, cv.CV_8U, removeData);
  const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
  cv.dilate(removeSmall, removeSmall, kernel);

  let removeMask = new cv.Mat();
  if (scale !== 1.0) {
    cv.resize(removeSmall, removeMask, new cv.Size(w, h), 0, 0, cv.INTER_NEAREST);
  } else {
    removeSmall.copyTo(removeMask);
  }

  cv.bitwise_and(removeMask, inkMask, removeMask);
  const removedPixels = cv.countNonZero(removeMask);
  const borderBand = Math.round(borderBandSmall / scale);

  const removeInv = new cv.Mat();
  const inkClean = new cv.Mat();
  cv.bitwise_not(removeMask, removeInv);
  cv.bitwise_and(inkMask, removeInv, inkClean);

  const cleanedBinary = new cv.Mat();
  if (inkInfo.inkValue === 255) {
    inkClean.copyTo(cleanedBinary);
  } else {
    cv.bitwise_not(inkClean, cleanedBinary);
  }

  inkMask.delete();
  if (ownSmall) {
    inkSmall.delete();
  }
  labels.delete();
  stats.delete();
  centroids.delete();
  removeSmall.delete();
  removeMask.delete();
  removeInv.delete();
  inkClean.delete();
  kernel.delete();

  return { cleanedBinary, removedPixels, borderBand };
}

function detectBbox(binaryMat, options) {
  const inkInfo = getInkInfo(binaryMat);
  const inkMask = matFromInk(binaryMat, inkInfo.inkValue);
  if (cv.countNonZero(inkMask) === 0) {
    inkMask.delete();
    return { bbox: null, info: null };
  }

  const h = inkMask.rows;
  const w = inkMask.cols;
  const longSide = Math.max(h, w);
  let scale = 1.0;
  let small = inkMask;
  let ownSmall = false;
  if (longSide > options.detectMaxSide) {
    scale = options.detectMaxSide / longSide;
    const smallW = Math.max(1, Math.round(w * scale));
    const smallH = Math.max(1, Math.round(h * scale));
    small = new cv.Mat();
    cv.resize(inkMask, small, new cv.Size(smallW, smallH), 0, 0, cv.INTER_NEAREST);
    ownSmall = true;
  }
  const smallW = small.cols;
  const smallH = small.rows;

  const rawCounts = reduceCounts(small);
  const rawRowRun = firstLastAbove(rawCounts.rowCounts, 1);
  const rawColRun = firstLastAbove(rawCounts.colCounts, 1);
  if (!rawRowRun || !rawColRun) {
    inkMask.delete();
    if (ownSmall) {
      small.delete();
    }
    return { bbox: null, info: null };
  }
  const rawTopS = rawRowRun[0];
  const rawBottomS = rawRowRun[1];
  const rawLeftS = rawColRun[0];
  const rawRightS = rawColRun[1];

  const opened = new cv.Mat();
  const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
  cv.morphologyEx(small, opened, cv.MORPH_OPEN, kernel);

  const effective = cv.countNonZero(opened) > 0 ? opened : small;
  const counts = reduceCounts(effective);

  const rowHigh = Math.max(4, Math.round(smallW * WEB_DEFAULTS.bboxProjRatio));
  const colHigh = Math.max(4, Math.round(smallH * WEB_DEFAULTS.bboxProjRatio));
  const rowLow = Math.max(2, Math.round(rowHigh * 0.35));
  const colLow = Math.max(2, Math.round(colHigh * 0.35));

  const rowRun = projectionBounds(counts.rowCounts, rowHigh, rowLow);
  const colRun = projectionBounds(counts.colCounts, colHigh, colLow);

  let topS;
  let bottomS;
  let leftS;
  let rightS;
  if (!rowRun || !colRun) {
    topS = rawTopS;
    bottomS = rawBottomS;
    leftS = rawLeftS;
    rightS = rawRightS;
  } else {
    topS = rowRun[0];
    bottomS = rowRun[1];
    leftS = colRun[0];
    rightS = colRun[1];

    const rawBoxHS = rawBottomS - rawTopS + 1;
    const rawBoxWS = rawRightS - rawLeftS + 1;
    const projBoxHS = bottomS - topS + 1;
    const projBoxWS = rightS - leftS + 1;

    if (projBoxWS < Math.round(rawBoxWS * options.minCoverRatio)) {
      leftS = rawLeftS;
      rightS = rawRightS;
    }
    if (projBoxHS < Math.round(rawBoxHS * options.minCoverRatio)) {
      topS = rawTopS;
      bottomS = rawBottomS;
    }
  }

  let left;
  let top;
  let right;
  let bottom;
  if (scale !== 1.0) {
    left = Math.floor(leftS / scale);
    top = Math.floor(topS / scale);
    right = Math.ceil((rightS + 1) / scale) - 1;
    bottom = Math.ceil((bottomS + 1) / scale) - 1;
  } else {
    left = leftS;
    top = topS;
    right = rightS;
    bottom = bottomS;
  }

  const rawBoxH = bottom - top + 1;
  const totalPad = Math.max(1, Math.round(rawBoxH * options.paddingRatio));
  left = clamp(left - totalPad, 0, w - 1);
  top = clamp(top - totalPad, 0, h - 1);
  right = clamp(right + totalPad, 0, w - 1);
  bottom = clamp(bottom + totalPad, 0, h - 1);

  let bbox = null;
  if (right > left && bottom > top) {
    bbox = { x: left, y: top, w: right - left + 1, h: bottom - top + 1 };
  }

  const info = {
    scale,
    detectW: smallW,
    detectH: smallH,
    rowHigh,
    colHigh,
    rawBoxH,
    totalPad,
  };

  inkMask.delete();
  if (ownSmall) {
    small.delete();
  }
  opened.delete();
  kernel.delete();
  return { bbox, info };
}

function detectSplitCandidates(inkRoiMat, detectMaxSide) {
  const h = inkRoiMat.rows;
  const w = inkRoiMat.cols;
  if (w <= 0 || h <= 0) {
    return { centers: [], info: { splitScale: 1, splitDetectW: 0, candidateCount: 0 } };
  }

  let scale = 1.0;
  let roiSmall = inkRoiMat;
  let ownSmall = false;
  if (w > detectMaxSide) {
    scale = detectMaxSide / w;
    const smallW = detectMaxSide;
    const smallH = Math.max(1, Math.round(h * scale));
    roiSmall = new cv.Mat();
    cv.resize(inkRoiMat, roiSmall, new cv.Size(smallW, smallH), 0, 0, cv.INTER_NEAREST);
    ownSmall = true;
  }
  const smallW = roiSmall.cols;

  const sums = new cv.Mat();
  cv.reduce(roiSmall, sums, 0, cv.REDUCE_SUM, cv.CV_32S);
  const proj = new Float32Array(smallW);
  for (let c = 0; c < smallW; c += 1) {
    proj[c] = sums.intPtr(0, c)[0] / 255.0;
  }
  sums.delete();

  const smooth = smoothProjection(proj);
  let maxVal = 0;
  for (let i = 0; i < smooth.length; i += 1) {
    if (smooth[i] > maxVal) {
      maxVal = smooth[i];
    }
  }
  if (maxVal <= 0) {
    if (ownSmall) {
      roiSmall.delete();
    }
    return {
      centers: [],
      info: { splitScale: scale, splitDetectW: smallW, candidateCount: 0 },
    };
  }

  const valleyThresh = percentile(smooth, WEB_DEFAULTS.splitPercentile);
  const valleyData = new Uint8Array(smallW);
  for (let i = 0; i < smallW; i += 1) {
    valleyData[i] = smooth[i] <= valleyThresh ? 255 : 0;
  }

  const valleyMat = cv.matFromArray(1, smallW, cv.CV_8U, valleyData);
  let closeK = Math.max(3, Math.round(smallW * 0.003));
  if (closeK % 2 === 0) {
    closeK += 1;
  }
  const closeKernel = cv.Mat.ones(1, closeK, cv.CV_8U);
  cv.morphologyEx(valleyMat, valleyMat, cv.MORPH_CLOSE, closeKernel);
  closeKernel.delete();

  const closed = Uint8Array.from(valleyMat.data);
  valleyMat.delete();
  const centersSmall = [];
  let start = -1;
  for (let i = 0; i < closed.length; i += 1) {
    const flag = closed[i] > 0;
    if (flag && start < 0) {
      start = i;
    } else if (!flag && start >= 0) {
      centersSmall.push(Math.floor((start + i - 1) / 2));
      start = -1;
    }
  }
  if (start >= 0) {
    centersSmall.push(Math.floor((start + closed.length - 1) / 2));
  }

  const edgeMargin = Math.max(2, Math.round(smallW * 0.01));
  const filtered = centersSmall.filter(
    (c) => c > edgeMargin && c < smallW - edgeMargin
  );

  let centers;
  if (scale !== 1.0) {
    centers = Array.from(new Set(filtered.map((c) => Math.round(c / scale)))).sort((a, b) => a - b);
  } else {
    centers = Array.from(new Set(filtered)).sort((a, b) => a - b);
  }
  centers = centers.filter((c) => c > 0 && c < w);

  if (ownSmall) {
    roiSmall.delete();
  }

  return {
    centers,
    info: { splitScale: scale, splitDetectW: smallW, candidateCount: centers.length },
  };
}

function buildColumnBoundaries(totalWidth, maxColWidth, splitCandidates) {
  const width = Math.max(1, Math.min(Math.floor(maxColWidth), Math.floor(totalWidth)));
  const minColWidth = Math.max(80, Math.round(width * 0.6));
  const minLeftWidth = Math.max(80, Math.round(width * 0.45));
  const candidates = Array.from(
    new Set(splitCandidates.filter((c) => c > 0 && c < totalWidth))
  ).sort((a, b) => a - b);

  const boundariesDesc = [totalWidth];
  let end = totalWidth;
  while (end > width) {
    const low = end - width;
    const high = end - minColWidth;
    const feasible = candidates.filter((c) => c >= low && c <= high);

    let split;
    if (feasible.length > 0) {
      split = feasible[0];
      for (const c of feasible) {
        const remaining = c;
        if (remaining >= minLeftWidth || remaining <= width) {
          split = c;
          break;
        }
      }
    } else {
      split = low;
    }

    if (split >= end) {
      split = Math.max(0, end - width);
      if (split >= end) {
        break;
      }
    }
    boundariesDesc.push(split);
    end = split;
  }
  if (boundariesDesc[boundariesDesc.length - 1] !== 0) {
    boundariesDesc.push(0);
  }

  const boundaries = Array.from(new Set(boundariesDesc)).sort((a, b) => a - b);
  if (boundaries[boundaries.length - 1] !== totalWidth) {
    boundaries.push(totalWidth);
  }
  return boundaries;
}

function matToCanvas(mat) {
  const canvas = document.createElement("canvas");
  canvas.width = mat.cols;
  canvas.height = mat.rows;
  cv.imshow(canvas, mat);
  return canvas;
}

function drawBoxedResult(sourceBgr, bbox, boundaries) {
  const boxed = sourceBgr.clone();
  if (!bbox) {
    return boxed;
  }
  const x = bbox.x;
  const y = bbox.y;
  const w = bbox.w;
  const h = bbox.h;
  for (let i = 1; i < boundaries.length - 1; i += 1) {
    const bx = x + boundaries[i];
    cv.line(
      boxed,
      new cv.Point(bx, y),
      new cv.Point(bx, y + h - 1),
      new cv.Scalar(255, 128, 0, 255),
      1
    );
  }
  cv.rectangle(
    boxed,
    new cv.Point(x, y),
    new cv.Point(x + w - 1, y + h - 1),
    new cv.Scalar(0, 0, 255, 255),
    2
  );
  return boxed;
}

async function runProcessing() {
  await ensureCvReady();

  if (!appState.sourceCanvas) {
    await loadSelectedImage();
  }
  if (!appState.sourceCanvas) {
    throw new Error("没有可处理的输入图。");
  }

  const options = parseOptions();
  setRuntime("处理中...");
  appendLog("开始执行图像管线");

  const t0 = performance.now();
  let sourceRgba;
  let sourceBgr;
  let gray;
  let blurred;
  let binaryInv;
  let binary;
  let binaryClean;
  let inkMask;
  let roi;

  try {
    sourceRgba = cv.imread(appState.sourceCanvas);
    sourceBgr = new cv.Mat();
    cv.cvtColor(sourceRgba, sourceBgr, cv.COLOR_RGBA2BGR);

    gray = new cv.Mat();
    cv.cvtColor(sourceBgr, gray, cv.COLOR_BGR2GRAY);

    blurred = new cv.Mat();
    cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0, 0, cv.BORDER_DEFAULT);

    binaryInv = new cv.Mat();
    cv.threshold(blurred, binaryInv, 0, 255, cv.THRESH_BINARY_INV + cv.THRESH_OTSU);

    const whiteArea = cv.countNonZero(binaryInv);
    const blackArea = binaryInv.rows * binaryInv.cols - whiteArea;

    binary = new cv.Mat();
    if (whiteArea > blackArea) {
      binaryInv.copyTo(binary);
    } else {
      cv.bitwise_not(binaryInv, binary);
    }

    const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
    cv.morphologyEx(binary, binary, cv.MORPH_OPEN, kernel);
    cv.morphologyEx(binary, binary, cv.MORPH_CLOSE, kernel);
    kernel.delete();

    const borderClean = removeBorderConnectedInk(binary);
    binaryClean = borderClean.cleanedBinary;

    const bboxRes = detectBbox(binaryClean, options);
    const bbox = bboxRes.bbox;

    let boundaries = [];
    let splitInfo = { candidateCount: 0 };
    let pages = 0;
    let maxColWidth = 0;

    if (bbox) {
      maxColWidth = Math.max(1, Math.min(Math.round(bbox.h / WEB_DEFAULTS.a4Ratio), bbox.w));
      const inkInfo = getInkInfo(binaryClean);
      inkMask = matFromInk(binaryClean, inkInfo.inkValue);
      roi = inkMask.roi(new cv.Rect(bbox.x, bbox.y, bbox.w, bbox.h));
      const splitRes = detectSplitCandidates(roi, options.detectMaxSide);
      splitInfo = splitRes.info;
      boundaries = buildColumnBoundaries(bbox.w, maxColWidth, splitRes.centers);
      pages = Math.max(0, boundaries.length - 1);
    }

    const boxed = drawBoxedResult(sourceBgr, bbox, boundaries);
    const binaryOutCanvas = matToCanvas(binaryClean);
    const boxOutCanvas = matToCanvas(boxed);
    boxed.delete();

    drawPreviewFromCanvas(binaryOutCanvas, dom.binaryCanvas);
    drawPreviewFromCanvas(boxOutCanvas, dom.boxCanvas);

    appState.result = {
      options,
      bbox,
      boundaries,
      pages,
      splitInfo,
      bboxInfo: bboxRes.info,
      removedPixels: borderClean.removedPixels,
      borderBand: borderClean.borderBand,
      binaryCanvas: binaryOutCanvas,
      boxCanvas: boxOutCanvas,
      sourceCanvas: appState.sourceCanvas,
    };

    setDownloadButtonsEnabled(true, Boolean(bbox));
    const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
    const mode = whiteArea > blackArea ? "白底黑字（无需反转）" : "黑底白字（已反转）";

    appendLog(`处理完成，耗时 ${elapsed}s，模式=${mode}`);
    if (bbox) {
      appendLog(
        `bbox: x=${bbox.x}, y=${bbox.y}, w=${bbox.w}, h=${bbox.h}, ` +
          `split_candidates=${splitInfo.candidateCount}, pages=${pages}`
      );
    } else {
      appendLog("未检测到有效墨迹框");
    }
    setRuntime(`处理完成（耗时 ${elapsed}s）`);
  } finally {
    if (sourceRgba) {
      sourceRgba.delete();
    }
    if (sourceBgr) {
      sourceBgr.delete();
    }
    if (gray) {
      gray.delete();
    }
    if (blurred) {
      blurred.delete();
    }
    if (binaryInv) {
      binaryInv.delete();
    }
    if (binary) {
      binary.delete();
    }
    if (binaryClean) {
      binaryClean.delete();
    }
    if (inkMask) {
      inkMask.delete();
    }
    if (roi) {
      roi.delete();
    }
  }
}

function downloadPdf() {
  if (!appState.result || !appState.result.bbox || !window.jspdf) {
    appendLog("当前没有可导出的 PDF 结果");
    return;
  }
  const { jsPDF } = window.jspdf;
  const { bbox, boundaries, sourceCanvas, options } = appState.result;
  const quality = clamp(options.jpegQuality / 100.0, 0.4, 1.0);
  const margin = options.marginMm;

  setRuntime("正在导出 PDF...");
  const doc = new jsPDF({
    orientation: "p",
    unit: "mm",
    format: "a4",
    compress: true,
  });

  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const usableW = pageW - margin * 2;
  const usableH = pageH - margin * 2;

  const segCanvas = document.createElement("canvas");
  const segCtx = segCanvas.getContext("2d");
  let pageCount = 0;

  for (let i = boundaries.length - 2; i >= 0; i -= 1) {
    const left = boundaries[i];
    const right = boundaries[i + 1];
    if (right <= left) {
      continue;
    }
    const segW = right - left;
    const segH = bbox.h;
    segCanvas.width = segW;
    segCanvas.height = segH;
    segCtx.clearRect(0, 0, segW, segH);
    segCtx.drawImage(
      sourceCanvas,
      bbox.x + left,
      bbox.y,
      segW,
      segH,
      0,
      0,
      segW,
      segH
    );

    const dataUrl = segCanvas.toDataURL("image/jpeg", quality);
    const scale = Math.min(usableW / segW, usableH / segH);
    const drawW = segW * scale;
    const drawH = segH * scale;
    const drawX = (pageW - drawW) / 2;
    const drawY = (pageH - drawH) / 2;

    if (pageCount > 0) {
      doc.addPage();
    }
    doc.addImage(dataUrl, "JPEG", drawX, drawY, drawW, drawH, undefined, "FAST");
    pageCount += 1;
  }

  const base = safeBaseName(appState.sourceName);
  doc.save(`${base}_a4_web.pdf`);
  setRuntime(`PDF 导出完成（${pageCount} 页）`);
  appendLog(`PDF 导出完成：${pageCount} 页`);
}

function bindEvents() {
  dom.fileInput.addEventListener("change", async () => {
    try {
      await loadSelectedImage();
      setRuntime("输入图已加载");
    } catch (error) {
      setRuntime(error.message, true);
      appendLog(`加载失败：${error.message}`);
    }
  });

  dom.runBtn.addEventListener("click", async () => {
    dom.runBtn.disabled = true;
    try {
      await runProcessing();
    } catch (error) {
      setRuntime(error.message || String(error), true);
      appendLog(`处理失败：${error.message || String(error)}`);
    } finally {
      dom.runBtn.disabled = false;
    }
  });

  dom.downloadBinaryBtn.addEventListener("click", () => {
    if (!appState.result) {
      return;
    }
    const base = safeBaseName(appState.sourceName);
    downloadCanvas(appState.result.binaryCanvas, `${base}_binary_web.png`);
  });

  dom.downloadBoxBtn.addEventListener("click", () => {
    if (!appState.result) {
      return;
    }
    const base = safeBaseName(appState.sourceName);
    downloadCanvas(appState.result.boxCanvas, `${base}_crop_box_web.png`);
  });

  dom.downloadPdfBtn.addEventListener("click", () => {
    try {
      downloadPdf();
    } catch (error) {
      setRuntime(error.message || String(error), true);
      appendLog(`PDF 导出失败：${error.message || String(error)}`);
    }
  });
}

async function boot() {
  initDomRefs();
  bindEvents();
  setDownloadButtonsEnabled(false, false);
  resetPreviewCanvas(dom.originalCanvas);
  resetPreviewCanvas(dom.binaryCanvas);
  resetPreviewCanvas(dom.boxCanvas);
  try {
    await ensureCvReady();
  } catch (error) {
    setRuntime(error.message, true);
    appendLog(`初始化失败：${error.message}`);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
