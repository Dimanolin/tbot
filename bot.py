from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from fuzzywuzzy import process
from models import QA, session
import nest_asyncio
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

nest_asyncio.apply()

MENU, ADD_QUESTION, ADD_ANSWER, SEARCH_QUESTION, DELETE_QUESTION = range(5)

def find_similar_question(user_question, limit=10, threshold=90):
    questions = [qa.question for qa in session.query(QA).all()]
    matches = process.extract(user_question, questions, limit=len(questions))
    filtered_matches = [(match[0], match[1]) for match in matches if match[1] >= threshold]
    if filtered_matches:
        similar_questions = [
            session.query(QA).filter(QA.question == match[0]).first()
            for match in filtered_matches
        ]
        return similar_questions[:limit], similar_questions[limit:]
    return [], []

async def start(update: Update, context:ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Добавить вопрос и ответ"],
        ["Найти ответ по вопросу"],
        ["Показать все вопросы"],
        ["Удалить вопрос"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие: ", reply_markup=reply_markup)
    return MENU

async def add_question(update: Update, context:ContextTypes.DEFAULT_TYPE):
    cancel_keyboard = [["Отмена"]]
    await update.message.reply_text(
        "Введите ваш вопрос(или нажмите 'Отмена' для выхода):", 
        reply_markup=ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True))
    return ADD_QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text.strip()
    if user_question.lower() == "отмена":
        context.user_data.pop('question', None)
        await update.message.reply_text(
            "Действие отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        return await start(update, context)

    context.user_data['question'] = user_question
    cancel_keyboard = [["Отмена"]]
    await update.message.reply_text(
        "Введите ответ на ваш вопрос (или нажмите 'Отмена' для выхода):",
        reply_markup=ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)
    )
    return ADD_ANSWER

async def save_answer(update:Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.text.strip().lower() == "отмена":
        await update.message.reply_text(
            "Действие отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await start(update, context)

    question = context.user_data.get('question')
    answer = update.message.text.strip()

    if question and answer:
        qa = QA(question=question, answer=answer)
        session.add(qa)
        session.commit()
        await update.message.reply_text(f"Вопрос и ответ добавлены! ID {qa.id}")
    else: 
        await update.message.reply_text("Что-то пошло не так. Попробуйте снова.")
    return await start(update, context)

async def search_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ваш вопрос:", reply_markup=ReplyKeyboardRemove())
    return SEARCH_QUESTION

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text.strip()
    top_matches, remaining_matches = find_similar_question(user_question)

    if top_matches:
        message = "Похожие вопросы:\n\n"
        for qa in top_matches:
            message += f"ID: {qa.id}\n\nВопрос: {qa.question}\n\nОтвет: {qa.answer}\n\n"
        
        if remaining_matches:
            context.user_data["remaining_matches"] = remaining_matches
            keyboard = [[InlineKeyboardButton("Показать все остальные", callback_data="show_more")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message)
    else:
        await update.message.reply_text("Похожий вопрос не найден.")
    return await start(update, context)

async def show_remaining_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    remaining_matches = context.user_data.get("remaining_matches", [])

    if remaining_matches:
        message = "Оставшиеся вопросы:\n\n"
        for qa in remaining_matches:
            message += f"ID: {qa.id}\n\nВопрос: {qa.question}\n\nОтвет: {qa.answer}\n\n"

        context.user_data.pop("remaining_matches", None)
        await query.edit_message_text(message)
    else:
        await query.edit_message_text("Нет оставшихся вопросов.")

async def show_all_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = session.query(QA).all()
    if not questions:
        await update.message.reply_text("В базе данных пока нет вопросов.")
        return MENU

    message_parts = []
    current_message = "Список всех вопросов и ответов:\n\n"

    for qa in questions:
        entry = f"ID: {qa.id}\n\nВопрос: {qa.question}\n\nОтвет: {qa.answer}\n\n"
        if len(current_message) + len(entry) > 4000:
            message_parts.append(current_message)
            current_message = ""
        current_message += entry
    
    if current_message:
        message_parts.append(current_message)
    
    for part in message_parts:
        await update.message.reply_text(part)

    return MENU


async def delete_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ID вопроса, который вы хотите удалить:", reply_markup=ReplyKeyboardRemove())
    return DELETE_QUESTION

async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        question_id = int(update.message.text.strip())
        question = session.query(QA).filter(QA.id == question_id).first()

        if question:
            session.delete(question)
            session.commit()
            await update.message.reply_text(f"Вопрос с ID {question_id} успешнно удалён.")
        else:
            await update.message.reply_text("Вопрос с таким ID не найден.")
    except ValueError:
        await update.message.reply_text("Некорректный ID. Попробуйте снова.")
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return await start(update, context)

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Начать$"), start),
            CommandHandler("start", start)],
        states={
            MENU: [
                MessageHandler(filters.Regex("^Добавить вопрос и ответ$"), add_question),
                MessageHandler(filters.Regex("^Найти ответ по вопросу$"), search_question),
                MessageHandler(filters.Regex("^Показать все вопросы$"), show_all_questions),
                MessageHandler(filters.Regex("^Удалить вопрос$"), delete_question),
            ],
            ADD_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_question), CommandHandler("cancel", cancel)],
            ADD_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_answer), CommandHandler("cancel", cancel)],
            SEARCH_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)],
            DELETE_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(MessageHandler(filters.Regex("^show_more$"), show_remaining_questions))
    
    application.add_handler(conv_handler)

    await application.run_polling()

if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
