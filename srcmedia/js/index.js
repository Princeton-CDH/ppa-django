import { Application } from '@hotwired/stimulus'
import NavController from './controllers/nav_controller'
import ClearableController from './controllers/clearable_controller'
import LazyLoadController from './controllers/lazy_load_controller'
import AboutNavController from './controllers/about_nav_controller'
import HistogramController from './controllers/histogram_controller'
import SearchController from './controllers/search_controller'
import TooltipController from './controllers/tooltip_controller'
import SelectController from './controllers/select_controller'
import 'fomantic-ui-less/semantic.less'

document.firstElementChild.classList.remove('no-js')

// Bootstrap Stimulus application
const application = Application.start()
application.register('nav', NavController)
application.register('clearable', ClearableController)
application.register('lazy-load', LazyLoadController)
application.register('about-nav', AboutNavController)
application.register('histogram', HistogramController)
application.register('search', SearchController)
application.register('tooltip', TooltipController)
application.register('select', SelectController)
