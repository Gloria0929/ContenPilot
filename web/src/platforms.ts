/** 平台英文标识 → 中文名映射（与后端 platforms 表 name 一致）。 */

export const PLATFORM_LABELS: Record<string, string> = {
  cnblogs: "博客园",
  juejin: "掘金",
  csdn: "CSDN",
  segmentfault: "思否",
  freebuf: "FreeBuf",
  baijiahao: "百家号",
  qiehao: "企鹅号",
  "51cto": "51CTO",
  tencent_cloud: "腾讯云开发者社区",
};

/** 显示名：中文名（英文标识），无映射时回退英文标识。 */
export function platformLabel(name: string | null | undefined): string {
  if (!name) return "";
  const zh = PLATFORM_LABELS[name];
  return zh ? `${zh}` : name;
}
