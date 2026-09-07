/// <reference types="vite/client" />

// CSS 副作用导入的类型声明（如 md-editor-v3/lib/style.css），
// 消除 IDE「找不到模块」的标红；vite 构建本身不依赖此文件。
declare module "*.css";
