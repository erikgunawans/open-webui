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

				<!-- JUP: the one thing a new chat should say before anything is typed. It describes
				     what the contract instructs (backend/jup/governance.py rules 1 and 2) rather than
				     promising what a model will do, and states the audit ADR-0002 enforces. -->
				<p class="mt-2 px-5 max-w-xl text-sm font-normal text-gray-600 dark:text-gray-400">
					{$i18n.t(
						'The assistant works under the JUP operating contract: it says what it does not know instead of inventing it, and never presents revenue as margin. Every request is logged.'
					)}
				</p>

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
