-- caption.lua: 给图片和表格自动加中文 caption 编号。
-- 图片：原 caption 前加 "图 N: "；表格：caption 设为 "表 N"。
-- 序号按文档出现顺序，单文档内连续。

local img_count = 0
local tbl_count = 0

-- 处理 Figure 元素（pandoc >= 2.10，带 caption 的图片为 Figure）
function Figure(el)
    img_count = img_count + 1
    local prefix = pandoc.Str(string.format("图 %d: ", img_count))
    if el.caption and el.caption.long and #el.caption.long > 0 then
        local first_block = el.caption.long[1]
        if first_block and first_block.content then
            -- 把 prefix 插到第一个 block 的 inline 列表最前面
            table.insert(first_block.content, 1, prefix)
        end
    end
    return el
end

-- 处理 Table 元素
function Table(el)
    tbl_count = tbl_count + 1
    local cap_text = string.format("表 %d", tbl_count)
    -- el.caption 是 pandoc.Caption（含 .long 和 .short）
    if el.caption then
        el.caption.long = pandoc.List({pandoc.Plain({pandoc.Str(cap_text)})})
        el.caption.short = pandoc.List({pandoc.Str(cap_text)})
    end
    return el
end
