from tools import (
    get_order_status, get_weather, calculate_date_difference, get_current_date
)
from schema import (
    OrderArgs, WeatherArgs, DateDiffArgs, CurrentDateArgs
)

TOOLS = [
    {
        'type'     : 'function',
        'function' : {
            'name'  : 'get_order_status',
            'description' : 'Return the customer order status of given order_id.',
            'parameters'  : {
                'type'   : 'object',
                'properties' : {
                    'order_id' : {'type' : 'string', 'description' : 'e.g. A0123'}
                },
                'required'   : ['order_id']
            }
        }
    },

    {
        'type'     : 'function',
        'function' : {
            'name'         : 'get_weather',
            'description'  : 'Get current weather condition of given city.',
            'parameters'   : {
                'type'  : 'object',
                'properties' : {
                    'city'  : {'type' : 'string', 'description' : 'e.g. Surat'}
                },
                'required' : ['city']
            } 
        }
    },

    {
        'type'     : 'function',
        'function' : {
            'name'         : 'calculate_date_difference',
            'description'  : 'Calculate the difference betweeen two given dates. in case you did not find start_date or end_date from user message than do not make any guess.',
            'parameters'   : {
                'type'       : 'object',
                'properties' : {
                    'start_date' : {'type' : 'string', 'description' : 'e.g. 25-02-2026'},
                    'end_date'   : {'type' : 'string', 'description' : 'e.g. 25-03-2027'}
                },
                'required'   : ['start_date', 'end_date']
            }
        }
    },

    {
        'type'     : 'function',
        'function' : {
            'name'         : 'get_current_date',
            'description'  : 'Get the current date.',
            'parameters'   : {
                'type'       : 'object',
                'properties' : {}
            }
        }
         
    }
]

TOOL_KIT = {
    'get_order_status'          : (OrderArgs,       get_order_status),
    'get_weather'               : (WeatherArgs,     get_weather),
    'calculate_date_difference' : (DateDiffArgs,    calculate_date_difference),
    'get_current_date'          : (CurrentDateArgs, get_current_date)
}