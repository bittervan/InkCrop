const WEB_DEFAULTS = {
  borderCleanMaxSide: 2400,
  borderBandRatio: 0.03,
  borderBandMin: 24,
  bboxProjRatio: 0.002,
  splitPercentile: 24,
  splitMinSpacing: 80,
  splitStrongValleyRatio: 0.45,
  splitStrongValleyMin: 12,
  splitRefineRadiusRatio: 0.4,
  splitRefineRadiusMin: 3,
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
  const webMaxSide = clamp(Number(dom.optWebMaxSide.value || 24000), 2000, 50000);
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
    const requestedScale = maxSide > options.webMaxSide ? options.webMaxSide / maxSide : 1;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });

    // 若浏览器无法承载目标尺寸，自动降级到可用分辨率。
    let scale = requestedScale;
    let targetW = 0;
    let targetH = 0;
    let loaded = false;
    for (let i = 0; i < 10; i += 1) {
      targetW = Math.max(1, Math.round(srcW * scale));
      targetH = Math.max(1, Math.round(srcH * scale));
      try {
        canvas.width = targetW;
        canvas.height = targetH;
        ctx.clearRect(0, 0, targetW, targetH);
        ctx.drawImage(image, 0, 0, targetW, targetH);
        // 触发一次读像素，尽早暴露潜在尺寸限制异常。
        ctx.getImageData(Math.min(targetW - 1, 0), Math.min(targetH - 1, 0), 1, 1);
        loaded = true;
        break;
      } catch (_) {
        scale *= 0.9;
      }
    }
    if (!loaded) {
      throw new Error("图片尺寸超出浏览器处理上限，请手动降低“网页最大边”。");
    }

    appState.sourceCanvas = canvas;
    appState.sourceName = file.name;
    appState.sourceOriginalSize = { width: srcW, height: srcH };
    appState.scaleFromOriginal = scale;

    drawPreviewFromCanvas(canvas, dom.originalCanvas);
    resetPreviewCanvas(dom.binaryCanvas);
    resetPreviewCanvas(dom.boxCanvas);
    setDownloadButtonsEnabled(false, false);
    appState.result = null;

    if (scale < requestedScale - 1e-6) {
      appendLog(
        `浏览器上限触发，自动降级到 ${targetW}x${targetH}（scale=${scale.toFixed(4)}）`
      );
    }
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

function estimateDominantSpacing(centers, candidateWidths, candidateCosts, strongCenters) {
  if (!strongCenters || strongCenters.length < 3) {
    return { spacing: null, confidence: 0 };
  }

  const sortedStrong = Array.from(strongCenters).sort((a, b) => a - b);
  const diffs = [];
  const pairWeights = [];
  for (let i = 0; i < sortedStrong.length - 1; i += 1) {
    diffs.push(sortedStrong[i + 1] - sortedStrong[i]);
    const c0 = sortedStrong[i];
    const c1 = sortedStrong[i + 1];
    const w0 = candidateWidths && candidateWidths[c0] ? candidateWidths[c0] : 1;
    const w1 = candidateWidths && candidateWidths[c1] ? candidateWidths[c1] : 1;
    const k0 = candidateCosts && candidateCosts[c0] !== undefined ? candidateCosts[c0] : 1;
    const k1 = candidateCosts && candidateCosts[c1] !== undefined ? candidateCosts[c1] : 1;
    const s0 = w0 / (1 + k0);
    const s1 = w1 / (1 + k1);
    const pairWeight = (s0 + s1) * 0.5;
    pairWeights.push(pairWeight);
  }
  if (diffs.length < 2) {
    return { spacing: null, confidence: 0 };
  }

  const q1 = percentile(diffs, 25);
  const q3 = percentile(diffs, 75);
  const iqr = Math.max(1, q3 - q1);
  const low = Math.max(WEB_DEFAULTS.splitMinSpacing, q1 - 1.5 * iqr);
  const high = q3 + 1.5 * iqr;

  const coreDiffs = [];
  const coreWeights = [];
  for (let i = 0; i < diffs.length; i += 1) {
    if (diffs[i] >= low && diffs[i] <= high) {
      coreDiffs.push(diffs[i]);
      coreWeights.push(pairWeights[i]);
    }
  }
  if (coreDiffs.length < 2) {
    return { spacing: null, confidence: 0 };
  }

  const medianStep = percentile(coreDiffs, 50);
  const binSize = Math.max(8, Math.round(medianStep * 0.08));
  const bins = new Map();
  let totalWeight = 0;
  for (let i = 0; i < coreDiffs.length; i += 1) {
    const b = Math.round(coreDiffs[i] / binSize);
    const prev = bins.get(b) || { weight: 0, values: [] };
    prev.weight += coreWeights[i];
    prev.values.push(coreDiffs[i]);
    bins.set(b, prev);
    totalWeight += coreWeights[i];
  }

  let bestBin = null;
  let bestWeight = -1;
  for (const [binId, payload] of bins.entries()) {
    if (payload.weight > bestWeight) {
      bestWeight = payload.weight;
      bestBin = binId;
    }
  }
  if (bestBin === null) {
    return { spacing: null, confidence: 0 };
  }

  const chosen = bins.get(bestBin).values;
  const spacing = Math.round(percentile(chosen, 50));
  if (spacing < WEB_DEFAULTS.splitMinSpacing) {
    return { spacing: null, confidence: 0 };
  }
  const confidence = Math.min(1, Math.max(0, bestWeight / (totalWeight + 1e-6)));
  return { spacing, confidence };
}

function estimateDominantPhase(centers, candidateWidths, candidateCosts, spacing) {
  if (!spacing || spacing <= 0 || !centers || centers.length === 0) {
    return null;
  }
  const residues = [];
  const weights = [];
  for (const c of centers) {
    const residue = c % spacing;
    const width = candidateWidths && candidateWidths[c] ? candidateWidths[c] : 1;
    const cost = candidateCosts && candidateCosts[c] !== undefined ? candidateCosts[c] : 1;
    residues.push(residue);
    weights.push(width / (1 + cost));
  }
  if (residues.length === 0) {
    return null;
  }

  const binSize = Math.max(6, Math.round(spacing * 0.08));
  const bins = new Map();
  for (let i = 0; i < residues.length; i += 1) {
    const b = Math.round(residues[i] / binSize);
    const prev = bins.get(b) || { weight: 0, residues: [] };
    prev.weight += weights[i];
    prev.residues.push(residues[i]);
    bins.set(b, prev);
  }

  let bestBin = null;
  let bestWeight = -1;
  for (const [binId, payload] of bins.entries()) {
    if (payload.weight > bestWeight) {
      bestWeight = payload.weight;
      bestBin = binId;
    }
  }
  if (bestBin === null) {
    return null;
  }
  const chosen = bins.get(bestBin).residues;
  return Math.round(percentile(chosen, 50));
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
  const runsSmall = [];
  let start = -1;
  for (let i = 0; i < closed.length; i += 1) {
    const flag = closed[i] > 0;
    if (flag && start < 0) {
      start = i;
    } else if (!flag && start >= 0) {
      const end = i - 1;
      runsSmall.push([Math.floor((start + end) / 2), end - start + 1]);
      start = -1;
    }
  }
  if (start >= 0) {
    const end = closed.length - 1;
    runsSmall.push([Math.floor((start + end) / 2), end - start + 1]);
  }

  const edgeMargin = Math.max(2, Math.round(smallW * 0.01));
  const filtered = runsSmall.filter(
    ([c]) => c > edgeMargin && c < smallW - edgeMargin
  );

  const candidateWidthsRaw = {};
  if (scale !== 1.0) {
    for (const [c, runW] of filtered) {
      const center = Math.round(c / scale);
      const width = Math.max(1, Math.round(runW / scale));
      if (center > 0 && center < w) {
        candidateWidthsRaw[center] = Math.max(candidateWidthsRaw[center] || 0, width);
      }
    }
  } else {
    for (const [c, runW] of filtered) {
      const center = Math.round(c);
      if (center > 0 && center < w) {
        candidateWidthsRaw[center] = Math.max(candidateWidthsRaw[center] || 0, runW);
      }
    }
  }

  if (Object.keys(candidateWidthsRaw).length === 0) {
    if (ownSmall) {
      roiSmall.delete();
    }
    return {
      centers: [],
      info: {
        splitScale: scale,
        splitDetectW: smallW,
        candidateCount: 0,
        candidateWidths: {},
        candidateCosts: {},
        dominantSpacing: null,
        dominantSpacingConf: 0,
        dominantPhase: null,
        strongCandidateCount: 0,
      },
    };
  }

  const fullSums = new cv.Mat();
  cv.reduce(inkRoiMat, fullSums, 0, cv.REDUCE_SUM, cv.CV_32S);
  const fullProj = new Float32Array(w);
  for (let c = 0; c < w; c += 1) {
    fullProj[c] = fullSums.intPtr(0, c)[0] / 255.0;
  }
  fullSums.delete();

  const candidateWidths = {};
  const candidateCosts = {};
  for (const [centerStr, widthRaw] of Object.entries(candidateWidthsRaw)) {
    const center = Number(centerStr);
    const width = Number(widthRaw);
    const refineR = Math.max(
      WEB_DEFAULTS.splitRefineRadiusMin,
      Math.round(width * WEB_DEFAULTS.splitRefineRadiusRatio)
    );
    const left = Math.max(0, center - refineR);
    const right = Math.min(w, center + refineR + 1);
    if (right <= left) {
      continue;
    }
    let bestIdx = left;
    let bestVal = fullProj[left];
    for (let i = left + 1; i < right; i += 1) {
      if (fullProj[i] < bestVal) {
        bestVal = fullProj[i];
        bestIdx = i;
      }
    }
    candidateWidths[bestIdx] = Math.max(candidateWidths[bestIdx] || 0, width);
    if (candidateCosts[bestIdx] === undefined || bestVal < candidateCosts[bestIdx]) {
      candidateCosts[bestIdx] = bestVal;
    }
  }

  const centers = Object.keys(candidateWidths)
    .map((k) => Number(k))
    .sort((a, b) => a - b);
  const keepN = Math.min(
    centers.length,
    Math.max(WEB_DEFAULTS.splitStrongValleyMin, Math.round(centers.length * WEB_DEFAULTS.splitStrongValleyRatio))
  );
  const strongCenters = centers
    .slice()
    .sort((a, b) => (candidateCosts[a] || 1e9) - (candidateCosts[b] || 1e9))
    .slice(0, keepN)
    .sort((a, b) => a - b);

  const spacingRes = estimateDominantSpacing(
    centers,
    candidateWidths,
    candidateCosts,
    strongCenters
  );
  const dominantPhase = estimateDominantPhase(
    strongCenters,
    candidateWidths,
    candidateCosts,
    spacingRes.spacing
  );

  if (ownSmall) {
    roiSmall.delete();
  }

  return {
    centers,
    info: {
      splitScale: scale,
      splitDetectW: smallW,
      candidateCount: centers.length,
      candidateWidths,
      candidateCosts,
      dominantSpacing: spacingRes.spacing,
      dominantSpacingConf: spacingRes.confidence,
      dominantPhase,
      strongCandidateCount: strongCenters.length,
    },
  };
}

function chooseSplitInWindow(
  feasible,
  end,
  targetWidth,
  candidateWidths,
  candidateCosts,
  costLow,
  costHigh,
  spacing,
  phase
) {
  if (!feasible || feasible.length === 0) {
    return null;
  }
  const widthValues = Object.values(candidateWidths || {});
  let maxScore = 1;
  if (widthValues.length > 0) {
    maxScore = Math.max(...widthValues);
  }

  let best = null;
  let bestCost = null;
  for (const c of feasible) {
    const segW = end - c;
    const widthCost = Math.abs(segW - targetWidth);

    let phaseCost = 0;
    if (spacing && phase !== null && spacing > 0) {
      const delta = Math.abs((c - phase) % spacing);
      phaseCost = Math.min(delta, spacing - delta);
    }

    const strength = (candidateWidths && candidateWidths[c] ? candidateWidths[c] : 1) / maxScore;
    const rawCost =
      candidateCosts && candidateCosts[c] !== undefined ? candidateCosts[c] : costHigh;
    const denom = Math.max(1, costHigh - costLow);
    let normCost = (rawCost - costLow) / denom;
    normCost = clamp(normCost, 0, 2);
    const cost = widthCost + 0.45 * phaseCost + 34.0 * normCost - 20.0 * strength;
    if (bestCost === null || cost < bestCost) {
      best = c;
      bestCost = cost;
    }
  }
  return best;
}

function buildColumnBoundaries(totalWidth, maxColWidth, splitCandidates, splitInfo) {
  const width = Math.max(1, Math.min(Math.floor(maxColWidth), Math.floor(totalWidth)));
  const minColWidth = Math.max(80, Math.round(width * 0.6));
  const minLeftWidth = Math.max(80, Math.round(width * 0.45));
  const candidates = Array.from(
    new Set(splitCandidates.filter((c) => c > 0 && c < totalWidth))
  ).sort((a, b) => a - b);

  const candidateWidths = (splitInfo && splitInfo.candidateWidths) || {};
  const candidateCosts = (splitInfo && splitInfo.candidateCosts) || {};
  const dominantSpacing = splitInfo && splitInfo.dominantSpacing ? splitInfo.dominantSpacing : null;
  const dominantSpacingConf =
    splitInfo && splitInfo.dominantSpacingConf ? splitInfo.dominantSpacingConf : 0;
  const dominantPhase =
    splitInfo && splitInfo.dominantPhase !== undefined ? splitInfo.dominantPhase : null;
  const useSpacing =
    Boolean(dominantSpacing) &&
    dominantSpacing > WEB_DEFAULTS.splitMinSpacing &&
    dominantSpacingConf >= 0.18;

  let phase = null;
  let targetWidth = width;
  if (useSpacing && candidates.length > 0) {
    phase = dominantPhase;
    if (phase === null || phase === undefined) {
      phase = candidates[candidates.length - 1] % dominantSpacing;
    }
    let linesPerCol = Math.max(1, Math.round(width / dominantSpacing));
    targetWidth = Math.round(linesPerCol * dominantSpacing);
    if (targetWidth > width && linesPerCol > 1) {
      linesPerCol -= 1;
      targetWidth = Math.round(linesPerCol * dominantSpacing);
    }
    if (targetWidth < minColWidth && (linesPerCol + 1) * dominantSpacing <= width) {
      linesPerCol += 1;
      targetWidth = Math.round(linesPerCol * dominantSpacing);
    }
    targetWidth = clamp(targetWidth, minColWidth, width);
  }

  const boundariesDesc = [totalWidth];
  let end = totalWidth;
  let costLow = 0;
  let costHigh = 1;
  const costValues = Object.values(candidateCosts);
  if (costValues.length > 0) {
    costLow = percentile(costValues, 15);
    costHigh = percentile(costValues, 85);
    if (costHigh <= costLow) {
      costHigh = costLow + 1;
    }
  }
  while (end > width) {
    const low = end - width;
    const high = end - minColWidth;
    let feasible = candidates.filter((c) => c >= low && c <= high);
    const feasibleValid = feasible.filter((c) => c >= minLeftWidth || c <= width);
    if (feasibleValid.length > 0) {
      feasible = feasibleValid;
    }

    let split;
    if (feasible.length > 0) {
      split = chooseSplitInWindow(
        feasible,
        end,
        targetWidth,
        candidateWidths,
        candidateCosts,
        costLow,
        costHigh,
        useSpacing ? dominantSpacing : null,
        phase
      );
      if (split === null) {
        split = feasible[0];
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
      boundaries = buildColumnBoundaries(
        bbox.w,
        maxColWidth,
        splitRes.centers,
        splitInfo
      );
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
      if (splitInfo.dominantSpacing) {
        appendLog(
          `line_spacing: spacing=${splitInfo.dominantSpacing}, conf=${splitInfo.dominantSpacingConf.toFixed(
            2
          )}`
        );
        appendLog(
          `strong_valleys: ${splitInfo.strongCandidateCount || 0}/${splitInfo.candidateCount || 0}`
        );
      }
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
