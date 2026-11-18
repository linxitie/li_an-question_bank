# 商品图抠像模型预下载（2026-11-18）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/shop/fetch_cutout_model.ps1            # general（973MB，质量最好）
#   powershell -ExecutionPolicy Bypass -File scripts/shop/fetch_cutout_model.ps1 -Variant lite  # lite（224MB，更快）
# 下载到 %USERPROFILE%\.rembg\models\<会话名>\，校验 MD5；离线/内网可先手动拷贝该目录。
param(
    [ValidateSet('general', 'lite')]
    [string]$Variant = 'general'
)

$ErrorActionPreference = 'Stop'

$models = @{
    general = @{
        Name = 'birefnet-general'
        Url  = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx'
        File = 'BiRefNet-general-epoch_244.onnx'
        Md5  = '7a35a0141cbbc80de11d9c9a28f52697'
        Size = 972666916
    }
    lite = @{
        Name = 'birefnet-general-lite'
        Url  = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx'
        File = 'birefnet-general-lite.onnx'
        Md5  = '4fab47adc4ff364be1713e97b7e66334'
        Size = 224005088
    }
}

$m = $models[$Variant]
$dir = Join-Path $env:USERPROFILE ('.rembg\models\' + $m.Name)
New-Item -ItemType Directory -Force $dir | Out-Null
$out = Join-Path $dir $m.File
$tmp = Join-Path $env:TEMP ('lian_cutout_' + $m.File)

if ((Test-Path $out) -and ((Get-Item $out).Length -eq $m.Size)) {
    "已存在：$out"
    exit 0
}

"下载 $($m.Name)（$([math]::Round($m.Size / 1MB)) MB）..."
for ($i = 1; $i -le 15; $i++) {
    curl.exe -L -C - --retry 20 --retry-all-errors -s -o $tmp $m.Url
    if ((Test-Path $tmp) -and ((Get-Item $tmp).Length -ge $m.Size)) { break }
    Start-Sleep -Seconds 2
}
if (-not (Test-Path $tmp) -or ((Get-Item $tmp).Length -lt $m.Size)) {
    throw "下载未完成：$tmp"
}
$md5 = (Get-FileHash $tmp -Algorithm MD5).Hash.ToLower()
if ($md5 -ne $m.Md5) { throw "MD5 校验失败：$md5 != $($m.Md5)" }
Move-Item $tmp $out -Force
"完成：$out"
"验证：python -c \"from app.services import product_image as m; print(m.cutout_engine())\""
