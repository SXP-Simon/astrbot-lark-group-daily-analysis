from lark_oapi.api.im.v1 import ListMessageRequest
from typing import List, Dict, Any

async def fetch_feishu_history_via_sdk(lark_client, container_id: str, start_time: int, end_time: int, page_size: int = 20, container_id_type: str = "chat") -> List[Dict[str, Any]]:
    print(f"[FeishuSDKDebug] params: container_id={container_id}, container_id_type={container_id_type}, start_time={start_time}, end_time={end_time}, page_size={page_size}")
    """
    使用 lark_oapi 官方 SDK 获取飞书历史消息
    :param lark_client: lark.Client 实例
    :param container_id: 群聊ID（oc_xxx）
    :param start_time: 开始时间（秒）
    :param end_time: 结束时间（秒）
    :param page_size: 每页消息数
    :param container_id_type: chat/user
    :return: 消息列表
    """
    items = []
    page_token = None
    while True:
        req_builder = ListMessageRequest.builder() \
            .container_id(container_id) \
            .container_id_type(container_id_type) \
            .start_time(int(start_time * 1000)) \
            .end_time(int(end_time * 1000)) \
            .page_size(page_size)
        if page_token:
            req_builder = req_builder.page_token(page_token)
        request = req_builder.build()
        response = await lark_client.im.v1.message.alist(request)
        print(f"[FeishuSDKDebug] response: code={getattr(response, 'code', None)}, msg={getattr(response, 'msg', None)}, data={getattr(response, 'data', None)}")
        if not response.success():
            raise Exception(f"Feishu SDK API error: {response.code} {response.msg}")
        batch = response.data.items or []
        items.extend(batch)
        if not response.data.has_more:
            break
        page_token = response.data.page_token
    print(f"[FeishuSDKDebug] total fetched messages: {len(items)}")
    return items
