"""
title: JUP documents
author: JUP operating layer (ent-os-new-jup)
version: 1.0.0
risk_class: write_own
description: Creates Word drafts on the JUP document templates (JUP Template Dokumen 2.0), owned by the asking user and attached to the answer.
"""

# This file is the tool as stored in the app's DB; deploy/gcp/sync-tools.ts pushes it. Tool code
# is exec'd in the backend where nothing tests it, so it stays a wrapper: every rule lives in
# `jup.office_tool` and `jup.office_doc` and is tested there.

from jup.office_tool import create_document as _create_document
from jup.office_tool import document_templates as _document_templates


class Tools:
    def document_templates(self, template: str = '') -> str:
        """
        List the JUP Word document templates, or show one template's structure (its headings and what belongs under each). Call it before create_document to choose a template and follow its structure.
        :param template: Optional template code, for example "MEM" (memo usulan keputusan) or "NOT" (notulen rapat). Leave empty for the list.
        :return: The template list, or the chosen template's outline.
        """
        return _document_templates(template)

    async def create_document(
        self,
        template: str,
        title: str,
        blocks: list[dict],
        classification: str = 'INTERNAL',
        unit: str = '',
        number: str = '',
        version: str = '',
        owner: str = '',
        date: str = '',
        distribution: str = '',
        __user__: dict | None = None,
        __request__=None,
        __chat_id__: str | None = None,
        __message_id__: str | None = None,
        __event_emitter__=None,
    ) -> str:
        """
        Create a Word document (.docx) draft on a JUP template and attach it to this answer for the user to download. Use it when the user asks for a document such as a memo, minutes, SOP, report or proposal. The document is always a draft (status Draf).
        :param template: Template code from document_templates, for example "MEM", "NOT", "SOP", "WHP".
        :param title: The document title.
        :param blocks: The body, in order. Each block is an object with "type": {"type":"heading","level":1|2|3,"text":...}, {"type":"paragraph","text":...}, {"type":"bullets","items":[...]}, {"type":"numbered","items":[...]}, {"type":"table","header":[...],"rows":[[...],...]}, {"type":"note","text":...}. Use **double asterisks** for bold. Write in Indonesian unless the user asks otherwise.
        :param classification: INTERNAL (default), TERBATAS or RAHASIA, following JUP's classification guide.
        :param unit: Issuing unit code for the document number, only if the user gave it.
        :param number: Document number, only if the user gave it.
        :param version: Version such as "0.1", only if the user gave it.
        :param owner: Document owner (person or unit), only if known.
        :param date: Document date as the user wants it written, only if known.
        :param distribution: Recipients, only if known.
        :return: Whether the document was created, and what the user should know about it.
        """
        return await _create_document(
            request=__request__,
            user=__user__,
            chat_id=__chat_id__,
            message_id=__message_id__,
            template=template,
            title=title,
            blocks=blocks,
            classification=classification,
            metadata={
                'unit': unit,
                'number': number,
                'version': version,
                'owner': owner,
                'date': date,
                'distribution': distribution,
            },
            emit=__event_emitter__,
        )
