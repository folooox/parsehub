import re

from ...provider_api.weibo import MediaType, MixMediaInfoItem, PicInfo, WeiboAPI
from ...types import (
    AniRef,
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    MultimediaParseResult,
    Platform,
    VideoParseResult,
    VideoRef,
)
from ..base.base import BaseParser


class WeiboParser(BaseParser):
    __platform__ = Platform.WEIBO
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)((m\.|)weibo\.(com|cn)/(?!(u/)).+|mapp\.api\.weibo\.cn/fx/.+)"

    async def _do_parse(self, raw_url: str) -> MultimediaParseResult | VideoParseResult | ImageParseResult:
        weibo = await WeiboAPI(self.proxy).parse(raw_url)
        data = weibo.data
        try:
            wb_user = getattr(data, "user", None) or {}
            if isinstance(wb_user, dict):
                wb_author        = (wb_user.get("screen_name") or wb_user.get("name") or "").strip() or None
                wb_author_handle = None  # 微博 uid 不作 handle 展示
            else:
                wb_author = wb_author_handle = None
        except Exception:
            wb_author = wb_author_handle = None
        text = self.f_text(data.content)
        media: list[VideoRef | ImageRef | LivePhotoRef | AniRef] = []

        if not data.pic_infos and data.page_info and data.page_info.object_type == MediaType.VIDEO:
            playback = data.page_info.media_info and data.page_info.media_info.playback
            if playback:
                vr = VideoParseResult(
                    content=text,
                    video=VideoRef(
                        url=playback.url,
                        thumb_url=data.page_info.page_pic,
                        width=playback.width,
                        height=playback.height,
                        duration=int(playback.duration),
                    ),
                )
                vr.author = wb_author
                return vr

        media_info: list[PicInfo | MixMediaInfoItem] | None = None
        if data.retweeted_status and data.retweeted_status.pic_infos:
            media_info = list(data.retweeted_status.pic_infos)
        elif data.pic_infos:
            media_info = list(data.pic_infos)
        elif data.mix_media_info and data.mix_media_info.items:
            media_info = list(data.mix_media_info.items)
        if not media_info:
            mr = MultimediaParseResult(content=text, media=[])
            mr.author = wb_author
            return mr

        for i in media_info:
            match i.type:
                case MediaType.VIDEO:
                    if i.media_url:
                        media.append(
                            VideoRef(
                                url=i.media_url,
                                thumb_url=i.thumb_url,
                                width=i.width,
                                height=i.height,
                                duration=i.duration,
                            )
                        )
                case MediaType.LIVE_PHOTO:
                    if i.thumb_url:
                        media.append(
                            LivePhotoRef(
                                url=i.thumb_url,
                                ext="mov",
                                video_url=i.media_url,
                                width=i.width,
                                height=i.height,
                            )
                        )
                case MediaType.GIF:
                    if i.media_url:
                        media.append(AniRef(url=i.media_url, thumb_url=i.thumb_url))
                case _:
                    if i.media_url:
                        media.append(ImageRef(url=i.media_url, thumb_url=i.thumb_url, width=i.width, height=i.height))
        if all((isinstance(m, ImageRef) or isinstance(m, LivePhotoRef)) for m in media):
            photos = [m for m in media if isinstance(m, ImageRef | LivePhotoRef)]
            final_result: ImageParseResult | MultimediaParseResult = ImageParseResult(content=text, photo=photos)
        else:
            final_result = MultimediaParseResult(content=text, media=media)
        final_result.author = wb_author
        return final_result

    def f_text(self, text: str | None) -> str:
        # text = re.sub(r'<a  href="https://video.weibo.com.*?>.*的微博视频.*</a>', "", text)
        # text = re.sub(r"<[^>]+>", " ", text)
        text = self.hashtag_handler(text or "")
        return text.strip()

    @staticmethod
    def hashtag_handler(desc: str) -> str:
        hashtags = re.findall(r" ?#[^#]+# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f" {hashtag.strip().removesuffix('#')} ")
        return desc


__all__ = ["WeiboParser"]
