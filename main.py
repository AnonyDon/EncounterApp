# TODO important:
#  edit button, typeError if fields left blank, noneError if nothing selected
#  improve layouts
#  after removing all rows, table loses the min width class????
# TODO unimportant:
#  turn tracking
#  turn timer
#  other picture tab that displays art (optional)
#  attack list
#  dice roller
import json
import webview
import os
from datetime import datetime as dt
from random import randint as rint
from typing import Dict
from nicegui import ui, events, app

# update these to dicts
round_number = 1
damage = 0
damage_str = 'Damage to Apply: '
selected = {'id': 0}
resources = {'has': False, }
table_props = "dense=False separator=cell table-header-style='background-color: #000000'"
table_props_dense = "dense separator=cell table-header-style='background-color: #000000'"
manual = {'is': False, }
edit_image_path = ""
last_removed = []
toggle_colors = {
    'damage': 'toggle-color=red-10',
    'heal': 'toggle-color=green-10',
    'temp': 'toggle-color=indigo-10',
    'vulnerable': 'toggle-color=orange-10',
    'normal': 'toggle-color=blue',
    'resistant': 'toggle-color=brown-10',
}


def dtwenty(mod=0, advantage=False, disadvantage=False):
    if advantage and disadvantage:
        result = rint(1, 20) + mod
    elif advantage:
        result = max(rint(1, 20) + mod, rint(1, 20) + mod)
    elif disadvantage:
        result = min(rint(1, 20) + mod, rint(1, 20) + mod)
    else:
        result = rint(1, 20) + mod
    return result


def update_round(next_round):
    global round_number
    if next_round:
        round_number += 1
        table.props(f'title="Round: {round_number}"')
    else:
        round_number = 1
        table.props(f'title="Round: {round_number}"')
    table.update()


def is_concentrating(e: events.GenericEventArguments):
    for row in rows:
        if row['id'] == e.args['id']:
            row['concentrating'] = e.args['concentrating']
    for x in table.selected:
        if x['id'] == e.args['id']:
            x['concentrating'] = e.args['concentrating']


def adjust_damage(num):
    if toggle2.value == 'vulnerable':
        adjusted_damage = num * 2
    elif toggle2.value == 'resistant':
        adjusted_damage = num // 2
    else:
        adjusted_damage = num
    return adjusted_damage


def enter(num):
    if toggle.value == 'damage':
        global damage, damage_str
        adjusted_damage = adjust_damage(num)
        damage += adjusted_damage
        damage_str += f'{adjusted_damage}, '
        reset_number()
    else:
        ui.notify('DAMAGE not selected, use APPLY')


def apply_change(sel):
    # grab variables
    global damage, damage_str
    log_num = 0
    # iterate through selected rows
    for row in sel:
        # grab the id of the row we are doing
        row_id = row['id']
        # we don't do damage to players or minions, make sure it's not those
        if row['type'] != 'player' and row['type'] != 'minion' and row['type'] != 'lair':
            # if we are set up to deal damage
            if toggle.value == 'damage':
                # gives us our damage to apply
                # if we don't have multiple damage types, means damage variable will be empty, so we apply what's in the
                # number input box directly, after adjusting it for resistances/vulnerabilities
                if damage == 0:
                    adjusted_damage = adjust_damage(number.value)
                else:
                    # if we use the damage variable, resistances and such are already applied
                    adjusted_damage = damage
                # concentration check, dc 10 unless 22 or greater damage, divide by 2 rounded down
                if row['concentrating']:
                    if adjusted_damage > 21:
                        concen_check_dc = adjusted_damage // 2
                    else:
                        concen_check_dc = 10
                    # prevents error is no conmod was entered
                    if row['conmod'] is None:
                        row['conmod'] = 0
                    # rolls the save and displays notification of result
                    concen_save = dtwenty(row['conmod'])
                    if concen_save < concen_check_dc:
                        row['concentrating'] = False
                        rows[row_id]['concentrating'] = row['concentrating']
                        ui.notify('FAILED CONCENTRATION CHECK')
                    else:
                        ui.notify('PASSES CONCENTRATION CHECK')
                    ui.notify(f'DC: {concen_check_dc} Save: {concen_save}')
                # log damage before reducing temp
                log_num = adjusted_damage
                # if there is temp hp, reduce it first before carrying over to hp, if it is greater than temp
                if row['temp'] > 0:
                    if adjusted_damage > row['temp']:
                        adjusted_damage -= row['temp']
                        row['temp'] = 0
                    else:
                        row['temp'] -= adjusted_damage
                        adjusted_damage = 0
                # checks to see if damage is enough to beat hp and applies relevant properties
                if adjusted_damage >= row['hp']:
                    row['hp'] = 0
                    row['conditions']['unconscious'] = True
                    row['concentrating'] = False
                    rows[row_id]['concentrating'] = row['concentrating']
                    rows[row_id]['conditions']['unconscious'] = row['conditions']['unconscious']
                # otherwise applies the damage
                else:
                    row['hp'] -= adjusted_damage
            # if we are set up to heal
            elif toggle.value == 'heal':
                if row['conditions']['unconscious']:
                    row['conditions']['unconscious'] = False
                    row['conditions']['incapacitated'] = False
                    rows[row_id]['conditions']['unconscious'] = row['conditions']['unconscious']
                    rows[row_id]['conditions']['incapacitated'] = row['conditions']['incapacitated']
                total = number.value + row['hp']
                if total >= row['hpmax']:
                    row['hp'] = row['hpmax']
                else:
                    row['hp'] += number.value
                log_num = number.value
            # if we are set to give temp hp
            elif toggle.value == 'temp':
                row['temp'] = number.value
                log_num = number.value
            rows[row_id]['hp'] = row['hp']
            rows[row_id]['temp'] = row['temp']
            # logs changes made to each row in sel
            log.push(f'{dt.now().strftime("%I:%M %p")}: Applied {log_num} {toggle.value} to {row["name"]}')
    damage = 0
    damage_str = 'Damage to Apply: '
    table.update()
    reset_number()


def reset_number():
    number.value = 0


def clear():
    reset_number()
    global damage, damage_str
    damage = 0
    damage_str = 'Damage to Apply: '


def reset_hp(sel):
    for a in sel:
        if a['type'] != 'player' and a['type'] != 'minion' and a['type'] != 'lair':
            rows[a['id']]['hp'] = a['hpmax']
            rows[a['id']]['conditions'] = ""
    table.selected = []


def append_number(num):
    if number.value == 0:
        number.value = num
    else:
        number.value = int(str(int(number.value)) + str(num))


# creates the elements
@ui.refreshable
def init_dialog_card():
    with ui.dialog() as init_dialog, ui.card():
        ui.label('Initiatives:')
        manual_checkbox = ui.checkbox('Manual?').bind_value(manual, 'is')
        with ui.scroll_area().classes('w-48 h-96'):
            for row in rows:
                if row['type'] == 'player':
                    ui.number(label=row['name']).props('clearable').bind_value(rows[row['id']], 'init')
                else:
                    ui.number(label=row['name']).props('clearable').bind_value(
                        rows[row['id']], 'init'
                    ).bind_visibility_from(manual_checkbox, 'value')
        ui.button('submit', on_click=lambda: init_dialog.submit('submit'))
    return init_dialog


# does the thing, waits for card
async def show_init_dialog():
    init_dialog_card.refresh()
    result = await init_dialog_card()
    if result == 'submit':
        if not manual['is']:
            for a in rows:
                if a['type'] != 'player' and a['type'] != 'lair':
                    if a['dexmod'] is None:
                        a['dexmod'] = 0
                    a['init'] = dtwenty(a["dexmod"])
        table.selected = []
    else:
        # init_dialog.close()
        ui.notify('Canceled')


# read the selected row's values, apply them to edit dialog components
# creates card, assign values
@ui.refreshable 
def edit_dialog_card():
    # check to see if there is anything selected
    try:
        row_id = table.selected[0]['id']
    except IndexError:
        ui.notify("Nothing Selected")
    else:
        with ui.dialog() as edit_dialog, ui.card().classes('min-w-max min-h-max'):
            with ui.row(wrap=False):
                with ui.column():
                    # checks for existing key, leave blank if not there, uses get() method
                    edit_type = ui.select(['enemy', 'boss', 'minion', 'player', 'lair', ], label='Type:',
                                          value=rows[row_id]['type'],
                                          ).classes('w-40')
                    edit_name = ui.input(label='Name:', value=rows[row_id].get('name'),)
                    edit_dexmod = ui.number(label="DEX mod:", value=rows[row_id].get('dexmod'),).props('clearable')
                    edit_conmod = ui.number(label="CON save:", value=rows[row_id].get('conmod'),).props('clearable')
                    edit_ac = ui.number(label="AC:", value=rows[row_id].get('ac'),).props('clearable')
                    edit_hpmax = ui.number(label="HP Max:", value=rows[row_id].get('hpmax'),).props('clearable')
                    edit_init = ui.number(label="Init.", value=rows[row_id].get('init'),).props('clearable')
                variables = {}
                with ui.column():
                    if rows[row_id]['resources']['has']:
                        for x in rows[row_id]['resources']:
                            if x == 'has':
                                continue
                            else:
                                # noinspection PyTypeChecker
                                variables[x] = rows[row_id]['resources'][x]['max']

                    def edit_res_enable_check():
                        # change enabled of the things
                        counter = 0
                        for element in element_list:
                            if edit_num_res.value > counter:
                                element.enable()
                            else:
                                element.disable()
                            counter += 1
                    edit_num_res = ui.select([0, 1, 2, 3, 4, 5], value=len(variables), label='Number of Resources',
                                             on_change=lambda: edit_res_enable_check()).classes('w-full')
                    with ui.scroll_area().classes('w-60 h-96'):
                        res_name = ui.input('Resource Name:')
                        res_max = ui.number('Resource Max:'
                                            ).classes('w-full').bind_enabled_from(res_name, 'enabled')
                        res_name2 = ui.input('Resource 2 Name:')
                        res_max2 = ui.number('Resource 2 Max:'
                                             ).classes('w-full').bind_enabled_from(res_name2, 'enabled')
                        res_name3 = ui.input('Resource 3 Name:')
                        res_max3 = ui.number('Resource 3 Max:'
                                             ).classes('w-full').bind_enabled_from(res_name3, 'enabled')
                        res_name4 = ui.input('Resource 4 Name:')
                        res_max4 = ui.number('Resource 4 Max:'
                                             ).classes('w-full').bind_enabled_from(res_name4, 'enabled')
                        res_name5 = ui.input('Resource 5 Name:')
                        res_max5 = ui.number('Resource 5 Max:'
                                             ).classes('w-full').bind_enabled_from(res_name5, 'enabled')
                        element_list = [res_name, res_name2, res_name3, res_name4, res_name5]

                        edit_res_enable_check()

                        if edit_num_res.value > 0:
                            res_name.value = list(variables.keys())[0]
                            res_max.value = list(variables.values())[0]
                        if edit_num_res.value > 1:
                            res_name2.value = list(variables.keys())[1]
                            res_max2.value = list(variables.values())[1]
                        if edit_num_res.value > 2:
                            res_name3.value = list(variables.keys())[2]
                            res_max3.value = list(variables.values())[2]
                        if edit_num_res.value > 3:
                            res_name4.value = list(variables.keys())[3]
                            res_max4.value = list(variables.values())[3]
                        if edit_num_res.value > 4:
                            res_name5.value = list(variables.keys())[4]
                            res_max5.value = list(variables.values())[4]

                with ui.column():
                    edit_img_path = ui.input(label="Image Path", value=rows[row_id].get('img'),).classes('w-full')

                    async def edit_img_selector():
                        file = await app.native.main_window.create_file_dialog()
                        ui.notify(f'{file[0]}')
                        edit_img_path.value = file[0]
                    ui.button('choose image', on_click=edit_img_selector)

                    def submit():
                        new_resources = {'has': False}
                        if edit_num_res.value > 0:
                            new_resources['has'] = True
                            new_resources[res_name.value] = {'value': res_max.value, 'max': res_max.value}
                        if edit_num_res.value > 1:
                            new_resources[res_name2.value] = {'value': res_max2.value, 'max': res_max2.value}
                        if edit_num_res.value > 2:
                            new_resources[res_name3.value] = {'value': res_max3.value, 'max': res_max3.value}
                        if edit_num_res.value > 3:
                            new_resources[res_name4.value] = {'value': res_max4.value, 'max': res_max4.value}
                        if edit_num_res.value > 4:
                            new_resources[res_name5.value] = {'value': res_max5.value, 'max': res_max5.value}
                        rows[row_id]['type'] = edit_type.value
                        rows[row_id]['name'] = edit_name.value
                        rows[row_id]['dexmod'] = edit_dexmod.value
                        rows[row_id]['conmod'] = edit_conmod.value
                        rows[row_id]['ac'] = edit_ac.value
                        rows[row_id]['hpmax'] = edit_hpmax.value
                        rows[row_id]['init'] = edit_init.value
                        rows[row_id]['img'] = edit_img_path.value
                        rows[row_id]['resources'] = new_resources
                        table.selected = []
                        edit_dialog.submit('submit')
                    ui.button('submit', on_click=lambda: submit()).classes(
                        'absolute-bottom-right m-5')
        return edit_dialog


# resets the edit card dialog, pulls it up, gives notification if applied or cancelled
async def edit():
    edit_dialog_card.refresh()
    result = await edit_dialog_card()
    if result == 'submit':
        ui.notify('Edit Applied')
    else:
        ui.notify('Canceled')


async def add_row():
    result = await add_row_dialog
    if result == 'submit':
        new_id = max((row['id'] for row in rows), default=-1) + 1
        new_dict = {
            'name': new_name.value.capitalize(), 'ac': new_ac.value,
            'dexmod': new_dexmod.value, 'conmod': new_conmod.value, 'id': new_id,
            'concentrating': False, 'type': new_type.value, 'hpmax': new_hpmax.value,
            'conditions': {**conditions}, 'img': new_img_path.value, 'temp': 0,
            'resources': {'has': resources_checkbox.value, }, 'init': None,
        }
        if new_dict['type'] != 'minion' and new_dict['type'] != 'player':
            if new_dict['type'] != 'lair':
                new_dict['hp'] = new_hpmax.value
            else:
                new_dict['init'] = 20
            if new_dict['resources']['has']:
                new_dict['resources'].update(
                    {resource_name.value: {'value': resource_value.value, 'max': resource_value.value, }}
                )
                if resource2_checkbox.value:
                    new_dict['resources'].update(
                        {resource2_name.value: {'value': resource2_value.value, 'max': resource2_value.value, }}
                    )
                if resource3_checkbox.value:
                    new_dict['resources'].update(
                        {resource3_name.value: {'value': resource3_value.value, 'max': resource3_value.value, }}
                    )
                if resource4_checkbox.value:
                    new_dict['resources'].update(
                        {resource4_name.value: {'value': resource4_value.value, 'max': resource4_value.value, }}
                    )
                if resource5_checkbox.value:
                    new_dict['resources'].update(
                        {resource5_name.value: {'value': resource5_value.value, 'max': resource5_value.value, }}
                    )
        ui.notify(f'added row with resources: {new_dict['resources']}')
        table.add_rows(new_dict)
        reset_row_ids()
        table.update()
    else:
        add_row_dialog.close()
        ui.notify('Canceled')


# sets all the row's in rows to have same id as their index
def reset_row_ids():
    x = -1
    for row in rows:
        x += 1
        row['id'] = x


def remove():
    global last_removed
    if not table.selected:
        ui.notify("Nothing selected")
    else:
        last_removed = table.selected.copy()
        table.remove_rows(*table.selected)
        reset_row_ids()
        removed_str = ""
        for row in last_removed:
            removed_str += f'{row['name']}, '
            pass
        undo_button.enable()
        log.push(f'{dt.now().strftime("%I:%M %p")}: Removed rows: {removed_str}')
        ui.notify(f'{last_removed}')


def undo():
    removed_str = ""
    for x in last_removed:
        table.add_rows(x)
        removed_str += f'{x['name']}, '
    reset_row_ids()
    undo_button.disable()
    log.push(f'{dt.now().strftime("%I:%M %p")}: Returned rows: {removed_str}')


def type_logic():
    if new_type.value == 'minion':
        resources_checkbox.value = False
        resources_checkbox.disable()
    else:
        resources_checkbox.enable()
    if new_type.value == 'lair':
        new_name.value = 'Lair Actions'
        new_ac.value = None
        new_ac.disable()
        new_hpmax.value = None
        new_hpmax.disable()
        new_conmod.value = None
        new_conmod.disable()
        new_dexmod.value = None
        new_dexmod.disable()
    else:
        new_dexmod.enable()
        new_conmod.enable()
        new_hpmax.enable()
        new_ac.enable()


def resources_toggle():
    if not resources_checkbox.value:
        resource2_checkbox.value = False
        resource3_checkbox.value = False
        resource4_checkbox.value = False
        resource5_checkbox.value = False


async def choose_file():
    file = await app.native.main_window.create_file_dialog(directory=f'{os.getcwd()}\\images',)
    ui.notify(f'{file[0]}')
    new_img_path.value = f'images/{os.path.basename(file[0])}'


def toggle_columns(column_: Dict, visible: bool):
    column_['classes'] = '' if visible else 'hidden'
    column_['headerClasses'] = '' if visible else 'hidden'
    table.update()


async def load():
    file = await app.native.main_window.create_file_dialog(
        dialog_type=webview.OPEN_DIALOG, directory=f'{os.getcwd()}\\saved',
    )
    try:
        with open(file[0], 'r') as fin:
            data = json.load(fin)
            rows.clear()
            rows.extend(data)
            table.update()
            selected['id'] = 0
            checkbox_card.refresh()
            log.push(f'{dt.now().strftime("%I:%M %p")}: Loaded Table: {os.path.basename(file[0])}')
    except TypeError:
        ui.notify('Canceled')


async def save():
    # file = await app.native.main_window.create_file_dialog(dialog_type=webview.SAVE_DIALOG)
    # ui.notify(f'{file}')
    # not sure how above works, how do I get the txt file?
    result = await save_dialog
    if result == 'submit':
        with open(f'saved/{filename.value}.txt', 'w') as fout:
            json.dump(rows, fout)
        save_dialog.close()
        ui.notify('Saved')
        log.push(f'{dt.now().strftime("%I:%M %p")}: Saved table as: {filename.value}.txt')
    else:
        save_dialog.close()
        ui.notify('Canceled')


def toggle_color(element):
    element.props(toggle_colors[element.value])


def row_clicked(e: events.GenericEventArguments):
    if e.args[1]['type'] != 'player':
        image.source = e.args[1]["img"]
        global selected
        selected.update({'id': e.args[1]['id']})
        checkbox_card.refresh()


def conditions_image():
    image.source = 'images/conditionsLong.png'


def conditions_logic(key):
    x = 0
    # ui.notify(key)
    for row in rows:
        if row['id'] == selected['id']:
            for thing in incapacitated_list:
                if row['conditions'][thing]:
                    row['conditions']['incapacitated'] = True
                    if thing == 'unconscious':
                        row['conditions']['prone'] = True
                else:
                    x += 1
            if key in incapacitated_list:
                if x == 4 and key != 'incapacitated':
                    row['conditions']['incapacitated'] = False


# noinspection PyUnresolvedReferences,PyShadowingNames,PyUnboundLocalVariable
@ui.refreshable
def checkbox_card() -> None:
    with ui.card().tight():
        with ui.row():
            for row in rows:
                if row['id'] == selected['id']:
                    with ui.column().classes('gap-3'):
                        ui.label(row['name'])
                        for key in row['conditions']:
                            ui.checkbox(key.capitalize(), on_change=lambda key=key: conditions_logic(key)
                                        ).bind_value(row['conditions'], key).props('dense')
                    if row['resources']['has']:
                        with ui.column():
                            for x in row['resources']:
                                if x == 'has':
                                    continue
                                # noinspection PyTypeChecker
                                options = [y for y in range(int(row['resources'][x]['max']) + 1)]
                                ui.select(label=x, options=options
                                          ).classes('w-28').props('dense').bind_value(row['resources'][x], 'value')
                    break


def dense():
    if dense_switch.value:
        table.props(table_props_dense)
    else:
        table.props(table_props)


def enlarge_image():
    large_image.set_source(image.source)
    image_dialog.open()


conditions = {
    'blinded': False,
    'charmed': False,
    'dazed': False,
    'deafened': False,
    'exhaustion': False,
    'frightened': False,
    'grappled': False,
    'incapacitated': False,
    'invisible': False,
    'paralyzed': False,
    'petrified': False,
    'poisoned': False,
    'prone': False,
    'restrained': False,
    'stunned': False,
    'unconscious': False,
}
incapacitated_list = ['paralyzed', 'petrified', 'stunned', 'unconscious']
columns = [
    {'name': 'init', 'label': 'Init.', 'field': 'init', 'sortable': True, 'align': 'center'},
    {'name': 'name', 'label': 'Name', 'field': 'name', 'required': True, 'align': 'left'},
    {'name': 'ac', 'label': 'AC', 'field': 'ac', 'align': 'left'},
    {'name': 'hpmax', 'label': 'HP Max', 'field': 'hpmax', 'align': 'left'},
    {'name': 'temp', 'label': 'Temp', 'field': 'temp', 'align': 'left'},
    {'name': 'hp', 'label': 'HP Current', 'field': 'hp', 'align': 'left'},
    {'name': 'concentrating', 'label': 'Concen?', 'align': 'left'},
]
rows = [
    {
        'id': 0, 'name': 'Player 1', 'ac': 18, 'type': 'player', 'concentrating': False, 'conditions': '',
        'resources': {**resources}, 'init': None,
    },
    {
        'id': 1, 'name': 'Player 2', 'ac': 16, 'type': 'player', 'concentrating': False, 'conditions': '',
        'resources': {**resources}, 'init': None,
    },
    {
        'id': 2, 'name': 'Player 3', 'ac': 18, 'type': 'player', 'concentrating': False, 'conditions': '',
        'resources': {**resources}, 'init': None,
     },
    {
        'id': 3, 'name': 'Player 4', 'ac': 16, 'type': 'player', 'concentrating': False, 'conditions': '',
        'resources': {**resources}, 'init': None,
     },
    {
        'id': 4, 'name': 'Enemy', 'ac': 12, 'dexmod': 2, 'conmod': 4, 'concentrating': False,
        'type': 'enemy', 'hpmax': 50, 'temp': 0, 'hp': 50, 'conditions': {**conditions}, 'resources': {**resources},
        'img': 'images/goblin.png',
    },
    {
        'id': 5, 'name': 'Enemy2', 'ac': 12, 'dexmod': 2, 'conmod': 4, 'concentrating': False,
        'type': 'enemy', 'hpmax': 50, 'temp': 0, 'hp': 50, 'conditions': {**conditions}, 'resources': {**resources},
        'img': 'images/goblin.png',
    },
    {
        'id': 6, 'name': 'Enemy3', 'ac': 12, 'dexmod': 2, 'conmod': 4, 'concentrating': False,
        'type': 'enemy', 'hpmax': 50, 'temp': 0, 'hp': 50, 'conditions': {**conditions}, 'resources': {**resources},
        'img': 'images/goblin.png',
    },
    {
        'id': 7, 'name': 'Enemy4', 'ac': 12, 'dexmod': 2, 'conmod': 4, 'concentrating': False,
        'type': 'enemy', 'hpmax': 50, 'temp': 0, 'hp': 50, 'conditions': {**conditions}, 'resources': {**resources},
        'img': 'images/goblin.png',
    },
    {
        'id': 8, 'name': 'Boss', 'ac': 19, 'dexmod': 2, 'conmod': 1,
        'concentrating': False, 'type': 'boss', 'hpmax': 150, 'temp': 0, 'hp': 150, 'conditions': {**conditions},
        'img': 'images/bargnot.png',
        'resources': {'has': True, 'Take My Pain': {'value': 3, 'max': 3}},
    },
    {
        'id': 9, 'name': 'Minions', 'ac': 10, 'dexmod': 2, 'conmod': 0, 'concentrating': False,
        'type': 'minion', 'hpmax': 8, 'conditions': {**conditions}, 'img': 'images/minion.png',
        'resources': {**resources},
    },
]

ui.dark_mode().enable()
app.native.settings['ALLOW_DOWNLOADS'] = True
ui.query('.nicegui-content').classes('p-0')

with ui.dialog() as add_row_dialog, ui.card().classes('min-w-max min-h-max'):
    # ui.label('New Entry:').classes('text-xl font-bold')
    with ui.row(wrap=False):
        new_type = ui.select(['enemy', 'boss', 'minion', 'player', 'lair', ], label='Type:', value='enemy',
                             on_change=lambda: type_logic(),
                             ).classes('w-40')
        resources_checkbox = ui.checkbox('Resources?', value=True, on_change=lambda: resources_toggle())
    with ui.row(wrap=False):
        with ui.column():
            new_name = ui.input(label='Name:')
            new_dexmod = ui.number(label="DEX mod:").props('clearable')
            new_conmod = ui.number(label="CON save:").props('clearable')
            new_ac = ui.number(label="AC:").props('clearable')
            new_hpmax = ui.number(label="HP Max:").props('clearable')
        with ui.scroll_area().classes('w-60 h-96'):
            resource_name = ui.input('Resource Name:').bind_enabled_from(resources_checkbox, 'value')
            resource_value = ui.number('Resource Max Value:', min=0, max=8
                                       ).bind_enabled_from(resources_checkbox, 'value').classes('w-full')
            resource2_checkbox = ui.checkbox('Resource 2?', value=False
                                             ).bind_enabled_from(resources_checkbox, 'value')
            resource2_name = ui.input('Resource 2 Name:').bind_enabled_from(resource2_checkbox, 'value')
            resource2_value = ui.number('Resource 2 Max Value:', min=0, max=8
                                        ).bind_enabled_from(resource2_checkbox, 'value').classes('w-full')
            resource3_checkbox = ui.checkbox('Resource 3?', value=False
                                             ).bind_enabled_from(resources_checkbox, 'value')
            resource3_name = ui.input('Resource 3 Name:').bind_enabled_from(resource3_checkbox, 'value')
            resource3_value = ui.number('Resource 3 Max Value:', min=0, max=8
                                        ).bind_enabled_from(resource3_checkbox, 'value').classes('w-full')
            resource4_checkbox = ui.checkbox('Resource 4?', value=False
                                             ).bind_enabled_from(resources_checkbox, 'value')
            resource4_name = ui.input('Resource 4 Name:').bind_enabled_from(resource4_checkbox, 'value')
            resource4_value = ui.number('Resource 4 Max Value:', min=0, max=8
                                        ).bind_enabled_from(resource4_checkbox, 'value').classes('w-full')
            resource5_checkbox = ui.checkbox('Resource 5?', value=False
                                             ).bind_enabled_from(resources_checkbox, 'value')
            resource5_name = ui.input('Resource 5 Name:').bind_enabled_from(resource5_checkbox, 'value')
            resource5_value = ui.number('Resource 5 Max Value:', min=0, max=8
                                        ).bind_enabled_from(resource5_checkbox, 'value').classes('w-full')
            type_logic()  # IDK if this is needed
        with ui.column():
            new_img_path = ui.input(label="Image Path").classes('w-full')
            ui.button('choose image', on_click=choose_file)
            ui.button('submit', on_click=lambda: add_row_dialog.submit('submit')).classes('absolute-bottom-right m-5')

with ui.dialog() as save_dialog, ui.card():
    filename = ui.input(label='Filename:', value='Encounter')
    with ui.row():
        ui.button('submit', on_click=lambda: save_dialog.submit('submit'))

with (ui.row(wrap=False).classes('w-full gap-1')):
    with ui.column():
        with ui.table(
                      title=f'Round: {round_number}', columns=columns, rows=rows, selection='multiple',
                      ).props(table_props).on('rowClick', row_clicked).classes('min-w-lg') as table:
            with table.add_slot('top-right'):
                ui.button('Reset', on_click=lambda: update_round(False)).props('dense').classes('h-1')
                ui.button('Next Round', on_click=lambda: update_round(True)
                          ).props('dense').props('dense').classes('h-1')
                dense_switch = ui.switch('Dense', on_change=lambda: dense()).props('dense')
        table.add_slot('body-cell-concentrating', '''
            <q-td key="concentrating" :props="props">
                <q-checkbox size="lg" dense v-model="props.row.concentrating" 
                    @update:model-value="() => $parent.$emit('is_concentrating', props.row)"
                />
            </q-td>
            ''')
        table.add_slot('body-cell-name', '''
            <q-td :props="props">
                <q-badge
                    :color="props.row.type == 'boss' ? 'red-10' : props.row.type == 'player' ? 'green-10'
                     : props.row.type == 'lair' ? 'blue-10' : props.row.type == 'minion' ? 'grey-9' : 'black'"
                    :style="props.row.hp == 0 ? 'text-decoration: line-through' : ''"
                >
                    {{ props.value }}
                </q-badge>
            </q-td>
        ''')
        table.on('is_concentrating', is_concentrating)
        with ui.grid(columns=5).classes('h-28'):
            ui.button('load', on_click=lambda: load())
            ui.button("Roll Init", on_click=show_init_dialog)
            ui.button('Remove', on_click=lambda: remove())
            ui.button('Add Row', on_click=add_row)
            with ui.button(icon='menu'):
                with ui.menu(), ui.column().classes('gap-0 p-2'):
                    for column in columns:
                        # noinspection PyUnresolvedReferences,PyShadowingNames,PyUnboundLocalVariable
                        ui.switch(column['label'], value=True,
                                  on_change=lambda e, column=column: toggle_columns(column, e.value))

            ui.button('save', on_click=save)
            ui.button('Reset HP', on_click=lambda: reset_hp(table.selected))
            undo_button = ui.button('un-rem', on_click=lambda: undo())
            undo_button.disable()
            ui.button('edit', on_click=edit)
            ui.button('close', on_click=app.shutdown)
        log = ui.log().classes('max-w-lg')
        log.push(f'{dt.now().strftime("%I:%M %p")}: App Started')

    with ui.column().classes('gap-1'):
        with ui.card().tight().classes('w-60'):
            with ui.grid(columns=3).classes('gap-1'):
                toggle2 = ui.toggle(['vulnerable', 'normal', 'resistant'], value='normal',
                                    on_change=lambda: toggle_color(toggle2)
                                    ).classes('col-span-full').props('color=black').props('dense')

                number = ui.number(label='Number', value=0, min=0, precision=0
                                   ).props('dense')
                ui.label().bind_text_from(globals(), 'damage_str').classes('col-span-2').props('dense')

                # toggle_color(toggle.value)
                toggle = ui.toggle(['damage', 'heal', 'temp'], value='damage',
                                   on_change=lambda: toggle_color(toggle)
                                   ).classes('col-span-2').props('color=black toggle-color=red-10 dense')
                ui.button("CLR", on_click=lambda: clear())

                ui.button("7", on_click=lambda: append_number(7))
                ui.button("8", on_click=lambda: append_number(8))
                ui.button("9", on_click=lambda: append_number(9))

                ui.button("4", on_click=lambda: append_number(4))
                ui.button("5", on_click=lambda: append_number(5))
                ui.button("6", on_click=lambda: append_number(6))

                ui.button("1", on_click=lambda: append_number(1))
                ui.button("2", on_click=lambda: append_number(2))
                ui.button("3", on_click=lambda: append_number(3))

                ui.button("0", on_click=lambda: append_number(0)).classes('col-span-2')
                ui.button("add", on_click=lambda: enter(number.value))

                ui.button("apply", on_click=lambda: apply_change(table.selected)).classes('col-span-full')
        checkbox_card()
        ui.button('Conditions', on_click=lambda: conditions_image()).props('dense')
    image = ui.image('images/goblin.png',).classes('h-screen').props(
        'fit=contain position="0 0"'
    ).on('click', lambda: enlarge_image())
with ui.dialog().classes('bg-black').props('maximized') as image_dialog:
    large_image = ui.image(
        image.source,
    ).classes('h-screen').props('fit=contain').on('click', image_dialog.close)
# fullscreen=True,
ui.run(title='Encounter App', native=True, reload=False,)
