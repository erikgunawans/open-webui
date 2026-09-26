<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	import { onMount, getContext, tick, createEventDispatcher } from 'svelte';
	import { blur, fade } from 'svelte/transition';

	const dispatch = createEventDispatcher();

	import { updateFolderById } from '$lib/apis/folders';

	import {
		config,
		user,
		models as _models,
		temporaryChatEnabled,
		selectedFolder
	} from '$lib/stores';
	import { refreshChatList, refreshFolderChatLists } from '$lib/stores/chatList';
	import { sanitizeResponseContent, extractCurlyBraceWords } from '$lib/utils';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import FolderPlaceholder from './Placeholder/FolderPlaceholder.svelte';
	import FolderTitle from './Placeholder/FolderTitle.svelte';
	import NoneJupeMark from './Placeholder/NoneJupeMark.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import { getKnowledgeById } from '$lib/apis/knowledge';

	const i18n = getContext('i18n');

	export let createMessagePair: Function;
	export let stopResponse: Function;

	export let autoScroll = false;

	export let atSelectedModel: Model | undefined;
	export let selectedModels: [''];

	export let history;

	export let prompt = '';
	export let files = [];
	export let messageInput = null;

	export let selectedToolIds = [];
	export let selectedSkillIds = [];
	export let selectedFilterIds = [];
	export let pendingOAuthTools = [];

	export let showCommands = false;

	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;
	export let webSearchEnabled = false;
	export let toolApprovalMode = 'full';
	export let onToolApprovalModeChange: Function = () => {};
	export let oauthRedirectHandler: Function = () => {};

	export let onUpload: Function = (e) => {};
	export let onUpdate: (data?: { file?: any }) => void = () => {};
	export let onSelect = (e) => {};
	export let onChange = (e) => {};
	export let onWebSearchToggle: Function = () => {};
	export let messageQueue: { id: string; prompt: string; files: any[] }[] = [];
	export let onQueueSendNow: (id: string) => void = () => {};
	export let onQueueEdit: (id: string) => void = () => {};
	export let onQueueDelete: (id: string) => void = () => {};
	export let askUser = {
		show: false,
		questions: [],
		allowOther: true,
		timeoutMs: null,
		onConfirm: (_value: any) => {},
		onCancel: () => {}
	};

	export let dragged = false;

	let models = [];
	let selectedModelIdx = 0;

	$: if (selectedModels.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = selectedModels.map((id) => $_models.find((m) => m.id === id));

	// JUP: greet by the time of day, as a colleague at JUP would: "Selamat pagi" until 11, "siang"
	// until 15, "sore" until 18, then "malam". The boundaries are the Indonesian ones, and each
	// branch is a literal t() call so the i18n extractor sees every key.
	const greeting = (name: string) => {
		const hour = new Date().getHours();
		if (hour >= 4 && hour < 11) return $i18n.t('Good morning, {{name}}', { name });
		if (hour >= 11 && hour < 15) return $i18n.t('Good day, {{name}}', { name });
		if (hour >= 15 && hour < 18) return $i18n.t('Good afternoon, {{name}}', { name });
		return $i18n.t('Good evening, {{name}}', { name });
	};
	// Naming $i18n here makes the greeting follow a language switch; first name only, because the
	// account holds the full legal name and a greeting is not a form.
	$: greetingText = $i18n && greeting(($user?.name ?? '').split(' ')[0]);

	// JUP: what the assistant knows, said before anything is typed. The topics mirror the files
	// sync-kb.ts generates into "JUP Strategy KB" (~/jup/kb: strategy, portfolio, partners, gas,
	// RUED). "Not connected" is the honest other half; update it when #23 attaches the decisions
	// server. Each topic is a starter, so the line is something to do rather than something to read.
	const JUP_KB_NAME = 'JUP Strategy KB';
	$: jupKb = (models[selectedModelIdx]?.info?.meta?.knowledge ?? []).find(
		(k) => k?.name === JUP_KB_NAME
	);
	$: knowledgeTopics = $i18n && [
		{
			label: $i18n.t('JUP strategy'),
			prompt: $i18n.t("What is JUP's current strategic direction, and what are its priorities?")
		},
		{
			label: $i18n.t('Project portfolio'),
			prompt: $i18n.t(
				"Summarise the status of JUP's project portfolio: gate, blockers, next steps."
			)
		},
		{
			label: $i18n.t('Partners'),
			prompt: $i18n.t("Who are JUP's main partners, and what role does each play?")
		},
		{
			label: $i18n.t('Gas & RUED'),
			prompt: $i18n.t("What are the key points in JUP's gas and RUED notes?")
		}
	];

	// The date comes from the collection itself, so it moves when sync-kb.ts runs. A user who
	// cannot read the collection simply sees no date: better silent than wrong.
	let kbUpdated = '';
	let kbFetchedFor = '';
	$: if (jupKb?.id && jupKb.id !== kbFetchedFor) {
		kbFetchedFor = jupKb.id;
		getKnowledgeById(localStorage.token, jupKb.id)
			.then((kb) => {
				kbUpdated = kb?.updated_at
					? new Intl.DateTimeFormat($i18n.language, { day: 'numeric', month: 'short' }).format(
							new Date(kb.updated_at * 1000)
						)
					: '';
			})
			.catch(() => {
				kbUpdated = '';
			});
	}

	// True when viewing a shared folder the current user doesn't own AND lacks write access
	$: folderReadOnly =
		$selectedFolder != null &&
		$selectedFolder.user_id !== $user?.id &&
		$selectedFolder.permission !== 'write';
</script>

<div class="m-auto w-full max-w-[58rem] px-1 @2xl:px-20 translate-y-6 py-24 text-center">
	{#if $temporaryChatEnabled}
		<Tooltip
			content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
			className="w-full flex justify-center mb-0.5"
			placement="top"
		>
			<div class="flex items-center gap-1.5 text-gray-500 text-xs my-1 w-fit">
				<EyeSlash strokeWidth="2" className="size-3.5" />{$i18n.t('Temporary Chat')}
			</div>
		</Tooltip>
	{/if}

	<div class="w-full text-3xl text-gray-800 dark:text-gray-100 text-center flex items-center gap-4">
		<div class="w-full flex flex-col justify-center items-center">
			{#if $selectedFolder}
				<FolderTitle
					folder={$selectedFolder}
					readOnly={folderReadOnly}
					onUpdate={async () => {
						await Promise.all([refreshChatList(localStorage.token), refreshFolderChatLists(null)]);
					}}
					onDelete={async () => {
						await Promise.all([refreshChatList(localStorage.token), refreshFolderChatLists(null)]);

						selectedFolder.set(null);
					}}
				/>
			{:else}
				<div class="flex flex-row justify-center gap-2.5 @sm:gap-3 w-fit px-5 max-w-xl">
					<div class="flex shrink-0 justify-center">
						<!-- JUP: with one model the avatar is decorative (aria-hidden, untabbable), so the
						     None-JUPe mark takes its place. Several models keep the vendor avatars, which
						     are the control for choosing between them. -->
						{#if models.length <= 1}
							<div class="mb-0.5" in:fade={{ duration: 100 }}>
								<NoneJupeMark className="size-9 @sm:size-10" />
							</div>
						{:else}
							<div class="flex -space-x-4 mb-0.5" in:fade={{ duration: 100 }}>
								{#each models as model, modelIdx}
									<Tooltip
										content={(models[modelIdx]?.info?.meta?.tags ?? [])
											.map((tag) => tag.name.toUpperCase())
											.join(', ')}
										placement="top"
									>
										<button
											aria-hidden={models.length <= 1}
											tabindex={models.length <= 1 ? -1 : 0}
											aria-label={$i18n.t('Get information on {{name}} in the UI', {
												name: models[modelIdx]?.name
											})}
											on:click={() => {
												selectedModelIdx = modelIdx;
											}}
										>
											<img
												src={`${WEBUI_API_BASE_URL}/models/model/profile/image?id=${model?.id}&lang=${$i18n.language}`}
												class=" size-9 @sm:size-10 rounded-2xl"
												aria-hidden="true"
												draggable="false"
												on:error={(e) => {
													// LICENSE covers this Open WebUI fallback logo.
													// Do not alter, remove, obscure, or replace it except as LICENSE permits:
													// https://docs.openwebui.com/license.
													e.currentTarget.src = '/favicon.png';
												}}
											/>
										</button>
									</Tooltip>
								{/each}
							</div>
						{/if}
					</div>

					<!-- JUP: a greeting, not the model slug, and the page's heading. First name only:
					     the account holds the full legal name, and a greeting is not a form. -->
					<h1
						class=" text-2xl @sm:text-2xl font-medium tracking-[-0.02em] line-clamp-1 flex items-center"
						in:fade={{ duration: 100 }}
					>
						{greetingText}
					</h1>
				</div>

				{#if jupKb}
					<!-- JUP: what it knows, as starters, then what it does not. -->
					<div class="mt-3 px-5 max-w-xl flex flex-col items-center gap-1.5 text-sm font-normal">
						<div class="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1.5">
							<span class="text-gray-600 dark:text-gray-400">{$i18n.t('Knows:')}</span>
							{#each knowledgeTopics as topic}
								<button
									type="button"
									class="rounded-full border border-gray-200 dark:border-gray-700 px-2.5 py-1 text-[13px] leading-none text-gray-700 dark:text-gray-200 hover:bg-gray-50 hover:border-gray-300 dark:hover:bg-gray-850 transition-colors"
									on:click={() => onSelect({ type: 'prompt', data: topic.prompt })}
								>
									{topic.label}
								</button>
							{/each}
							{#if kbUpdated}
								<span class="text-xs text-gray-600 dark:text-gray-400"
									>· {$i18n.t('updated {{date}}', { date: kbUpdated })}</span
								>
							{/if}
						</div>
						<p class="text-xs text-gray-600 dark:text-gray-400">
							{$i18n.t('Not connected yet: email, live finance, BOD decisions.')}
						</p>
					</div>
				{/if}

				<!-- JUP: the operating contract as a stance (backend/jup/governance.py rules 1 and 2),
				     and the logging stated exactly: jup.governance records who, when, model and tools
				     (argument size only, never content) in Cloud Logging's 30-day _Default bucket.
				     ENABLE_ADMIN_CHAT_ACCESS is off (deploy.sh), which is what makes the history line
				     complete. Change any of those and this copy is wrong. -->
				<div class="mt-3 px-5 max-w-xl text-sm font-normal text-gray-600 dark:text-gray-400">
					<p>
						{$i18n.t("Honest about what it doesn't know, and never presents revenue as profit.")}
					</p>
					<details class="group mt-1 text-xs">
						<summary
							class="mx-auto w-fit cursor-pointer list-none inline-flex items-center gap-1 rounded-sm underline decoration-gray-300 dark:decoration-gray-600 underline-offset-4 hover:text-gray-800 dark:hover:text-gray-200 [&::-webkit-details-marker]:hidden"
						>
							{$i18n.t('What is logged?')}
							<ChevronDown
								className="size-3 transition-transform group-open:rotate-180"
								strokeWidth="2.5"
							/>
						</summary>
						<ul
							class="mt-2 mx-auto w-fit max-w-md text-left list-disc ps-4 space-y-1 leading-relaxed"
						>
							<li>
								{$i18n.t(
									'Who asked, when, which model, and which tools were used. What you ask is not part of this record.'
								)}
							</li>
							<li>{$i18n.t('This record is kept for 30 days for governance audit.')}</li>
							<li>
								{$i18n.t(
									'Conversations are saved in your history. Temporary chats are not saved to history.'
								)}
							</li>
						</ul>
					</details>
				</div>

				<div class="flex mt-1 mb-2">
					<div in:fade={{ duration: 100, delay: 50 }}>
						{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
							<Tooltip
								className=" w-fit"
								content={DOMPurify.sanitize(
									marked.parse(
										sanitizeResponseContent(
											models[selectedModelIdx]?.info?.meta?.description ?? ''
										).replaceAll('\n', '<br>')
									)
								)}
								placement="top"
							>
								<div
									class="mt-0.5 px-2 text-sm font-normal text-gray-500 dark:text-gray-400 line-clamp-2 max-w-xl markdown"
								>
									{@html DOMPurify.sanitize(
										marked.parse(
											sanitizeResponseContent(
												models[selectedModelIdx]?.info?.meta?.description ?? ''
											).replaceAll('\n', '<br>')
										)
									)}
								</div>
							</Tooltip>

							{#if models[selectedModelIdx]?.info?.meta?.user}
								<div class="mt-0.5 text-sm font-normal text-gray-400 dark:text-gray-500">
									By
									{#if models[selectedModelIdx]?.info?.meta?.user.community}
										<a
											href="https://openwebui.com/m/{models[selectedModelIdx]?.info?.meta?.user
												.username}"
											>{models[selectedModelIdx]?.info?.meta?.user.name
												? models[selectedModelIdx]?.info?.meta?.user.name
												: `@${models[selectedModelIdx]?.info?.meta?.user.username}`}</a
										>
									{:else}
										{models[selectedModelIdx]?.info?.meta?.user.name}
									{/if}
								</div>
							{/if}
						{/if}
					</div>
				</div>
			{/if}

			<div class="text-base font-normal @md:max-w-3xl w-full py-3 {atSelectedModel ? 'mt-2' : ''}">
				{#if !($selectedFolder && folderReadOnly)}
					<MessageInput
						bind:this={messageInput}
						{history}
						bind:selectedModels
						bind:files
						bind:prompt
						bind:autoScroll
						bind:selectedToolIds
						bind:selectedSkillIds
						bind:selectedFilterIds
						bind:imageGenerationEnabled
						bind:codeInterpreterEnabled
						bind:webSearchEnabled
						bind:atSelectedModel
						bind:showCommands
						bind:dragged
						{pendingOAuthTools}
						{oauthRedirectHandler}
						{toolApprovalMode}
						{onToolApprovalModeChange}
						{stopResponse}
						{createMessagePair}
						placeholder={$i18n.t('Attach a document or ask a question…')}
						{onChange}
						{onUpload}
						{onUpdate}
						{messageQueue}
						{onQueueSendNow}
						{onQueueEdit}
						{onQueueDelete}
						{askUser}
						{onWebSearchToggle}
						on:chatVariables
						on:submit={(e) => {
							dispatch('submit', e.detail);
						}}
					/>
				{/if}
			</div>
		</div>
	</div>

	{#if $selectedFolder}
		<div class="mx-auto px-4 md:max-w-3xl md:px-6 min-h-62" in:fade={{ duration: 200, delay: 200 }}>
			<FolderPlaceholder folder={$selectedFolder} />
		</div>
	{:else}
		<!-- JUP: the same width as the input above, so the suggestions share its left edge. -->
		<div class="mx-auto w-full @md:max-w-3xl mt-2" in:fade={{ duration: 200, delay: 200 }}>
			<div class="mx-2">
				<Suggestions
					suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
						models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
						$config?.default_prompt_suggestions ??
						[]}
					inputValue={prompt}
					{onSelect}
				/>
			</div>
		</div>
	{/if}
</div>
